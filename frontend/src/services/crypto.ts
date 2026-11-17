// DropSafe Client-Side Web Crypto Subsystem
// Zero-knowledge envelope encryption, key generation, and IndexedDB persistence

const DB_NAME = 'dropsafe_key_store';
const DB_VERSION = 1;
const STORE_NAME = 'crypto_keys';

// ----------------------------------------------------------------------
// IndexedDB Local Private Key Storage
// ----------------------------------------------------------------------
function openKeyDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function storeLocalKey(keyId: string, key: CryptoKey): Promise<void> {
  const db = await openKeyDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(key, keyId);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getLocalKey(keyId: string): Promise<CryptoKey | null> {
  const db = await openKeyDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.get(keyId);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

// ----------------------------------------------------------------------
// Buffer & Hex / Base64 Helpers
// ----------------------------------------------------------------------
export function bufferToHex(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export function hexToBuffer(hex: string): Uint8Array {
  const clean = hex.startsWith('0x') ? hex.slice(2) : hex;
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < clean.length; i += 2) {
    bytes[i / 2] = parseInt(clean.substring(i, i + 2), 16);
  }
  return bytes;
}

export function bufferToBase64(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export function base64ToBuffer(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ----------------------------------------------------------------------
// User Key Generation & Registration
// ----------------------------------------------------------------------
export interface UserGeneratedKeys {
  encryptionKeyPair: CryptoKeyPair;
  signingKeyPair: CryptoKeyPair;
  encryptionPublicJwk: JsonWebKey;
  signingPublicJwk: JsonWebKey;
}

export async function generateUserKeyPairs(): Promise<UserGeneratedKeys> {
  // 1. RSA-OAEP-3072 Encryption Key Pair (used to wrap/unwrap DEKs)
  const encryptionKeyPair = await window.crypto.subtle.generateKey(
    {
      name: 'RSA-OAEP',
      modulusLength: 3072,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    true,
    ['wrapKey', 'unwrapKey', 'encrypt', 'decrypt']
  );

  // 2. ECDSA-P256 Signing Key Pair (used to sign version commitments)
  const signingKeyPair = await window.crypto.subtle.generateKey(
    {
      name: 'ECDSA',
      namedCurve: 'P-256',
    },
    true,
    ['sign', 'verify']
  );

  const encryptionPublicJwk = await window.crypto.subtle.exportKey('jwk', encryptionKeyPair.publicKey);
  const signingPublicJwk = await window.crypto.subtle.exportKey('jwk', signingKeyPair.publicKey);

  return {
    encryptionKeyPair,
    signingKeyPair,
    encryptionPublicJwk,
    signingPublicJwk,
  };
}

export async function saveUserPrivateKeys(userId: string, keys: UserGeneratedKeys): Promise<void> {
  await storeLocalKey(`enc_priv_${userId}`, keys.encryptionKeyPair.privateKey);
  await storeLocalKey(`enc_pub_${userId}`, keys.encryptionKeyPair.publicKey);
  await storeLocalKey(`sig_priv_${userId}`, keys.signingKeyPair.privateKey);
  await storeLocalKey(`sig_pub_${userId}`, keys.signingKeyPair.publicKey);
}

export async function getUserPrivateKey(userId: string, purpose: 'encryption' | 'signing'): Promise<CryptoKey | null> {
  const prefix = purpose === 'encryption' ? 'enc_priv_' : 'sig_priv_';
  return getLocalKey(`${prefix}${userId}`);
}

// ----------------------------------------------------------------------
// Zero-Knowledge Document Encryption & Decryption
// ----------------------------------------------------------------------
export interface EncryptedPackage {
  ciphertext: ArrayBuffer;
  ciphertextSha256Hex: string;
  ciphertextSizeBytes: number;
  dek: CryptoKey;
  manifest: {
    algorithm: string;
    iv_base64: string;
    chunk_size: number;
    total_size: number;
  };
}

export async function encryptFile(file: File): Promise<EncryptedPackage> {
  // 1. Generate ephemeral 256-bit AES-GCM Document Encryption Key (DEK)
  const dek = await window.crypto.subtle.generateKey(
    {
      name: 'AES-GCM',
      length: 256,
    },
    true,
    ['encrypt', 'decrypt']
  );

  // 2. Read file bytes
  const fileBytes = await file.arrayBuffer();

  // 3. Generate random 12-byte IV for AES-GCM
  const iv = window.crypto.getRandomValues(new Uint8Array(12));

  // 4. Encrypt file bytes
  const ciphertext = await window.crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv,
    },
    dek,
    fileBytes
  );

  // 5. Compute SHA-256 digest of ciphertext
  const hashBuffer = await window.crypto.subtle.digest('SHA-256', ciphertext);
  const ciphertextSha256Hex = bufferToHex(hashBuffer);

  return {
    ciphertext,
    ciphertextSha256Hex,
    ciphertextSizeBytes: ciphertext.byteLength,
    dek,
    manifest: {
      algorithm: 'AES-256-GCM',
      iv_base64: bufferToBase64(iv),
      chunk_size: file.size,
      total_size: file.size,
    },
  };
}

export async function wrapDek(dek: CryptoKey, recipientPublicJwk: JsonWebKey): Promise<string> {
  const recipientKey = await window.crypto.subtle.importKey(
    'jwk',
    recipientPublicJwk,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256',
    },
    true,
    ['wrapKey']
  );

  const wrappedBuffer = await window.crypto.subtle.wrapKey('raw', dek, recipientKey, {
    name: 'RSA-OAEP',
  });

  return bufferToBase64(wrappedBuffer);
}

export async function unwrapDek(wrappedDekBase64: string, privateRsaKey: CryptoKey): Promise<CryptoKey> {
  const wrappedBytes = base64ToBuffer(wrappedDekBase64);

  return window.crypto.subtle.unwrapKey(
    'raw',
    wrappedBytes as unknown as BufferSource,
    privateRsaKey,
    {
      name: 'RSA-OAEP',
    },
    {
      name: 'AES-GCM',
      length: 256,
    },
    true,
    ['encrypt', 'decrypt']
  );
}

export async function decryptFile(
  ciphertext: ArrayBuffer,
  dek: CryptoKey,
  manifest: { iv_base64: string }
): Promise<ArrayBuffer> {
  const iv = base64ToBuffer(manifest.iv_base64);

  return window.crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: iv as unknown as BufferSource,
    },
    dek,
    ciphertext
  );
}

export async function signDigest(digestHex: string, privateEcdsaKey: CryptoKey): Promise<string> {
  const digestBytes = hexToBuffer(digestHex);
  const sigBuffer = await window.crypto.subtle.sign(
    {
      name: 'ECDSA',
      hash: { name: 'SHA-256' },
    },
    privateEcdsaKey,
    digestBytes as unknown as BufferSource
  );

  return bufferToHex(sigBuffer);
}

export const cryptoService = {
  generateUserKeyPairs,
  saveUserPrivateKeys,
  getUserPrivateKey,
  storeLocalKey,
  getLocalKey,
  encryptFile,
  wrapDek,
  unwrapDek,
  decryptFile,
  signDigest,
  bufferToHex,
  hexToBuffer,
  bufferToBase64,
  base64ToBuffer,
  async hasKeys(): Promise<boolean> {
    const db = await openKeyDatabase();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.count();
      req.onsuccess = () => resolve(req.result > 0);
      req.onerror = () => resolve(false);
    });
  },
  async unwrapKey(wrappedDekBase64: string): Promise<CryptoKey> {
    const db = await openKeyDatabase();
    const privKey: CryptoKey = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.openCursor();
      req.onsuccess = () => {
        const cursor = req.result;
        if (cursor) {
          if (typeof cursor.key === 'string' && cursor.key.startsWith('enc_priv_')) {
            resolve(cursor.value);
            return;
          }
          cursor.continue();
        } else {
          reject(new Error('No private encryption key found in browser storage'));
        }
      };
      req.onerror = () => reject(req.error);
    });
    return unwrapDek(wrappedDekBase64, privKey);
  },
};
