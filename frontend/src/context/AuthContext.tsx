import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, userApi, getAccessToken } from '../services/api';
import {
  generateUserKeyPairs,
  saveUserPrivateKeys,
  getUserPrivateKey,
} from '../services/crypto';
import type { UserProfileResponse, UserKeyResponse } from '../types/api';

interface AuthContextType {
  user: UserProfileResponse | null;
  keys: UserKeyResponse[];
  isAuthenticated: boolean;
  isLoading: boolean;
  activeEncryptionKeyId: string | null;
  activeSigningKeyId: string | null;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  ensureKeysSetUp: () => Promise<void>;
  initializeCryptoKeys: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [keys, setKeys] = useState<UserKeyResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const activeEncryptionKey = keys.find((k) => k.key_purpose === 'encryption' && k.status === 'active');
  const activeSigningKey = keys.find((k) => k.key_purpose === 'signing' && k.status === 'active');

  const ensureKeysSetUp = async (targetUser?: UserProfileResponse) => {
    const currentUser = targetUser || user;
    if (!currentUser) return;

    try {
      const myKeys = await userApi.getMyKeys();
      setKeys(myKeys);

      const hasEnc = myKeys.some((k) => k.key_purpose === 'encryption' && k.status === 'active');
      const hasSig = myKeys.some((k) => k.key_purpose === 'signing' && k.status === 'active');

      // Check if we already have private keys in IndexedDB
      const existingEncPriv = await getUserPrivateKey(currentUser.id, 'encryption');

      if (!hasEnc || !hasSig || !existingEncPriv) {
        console.log('[DropSafe Crypto] Initializing and registering browser cryptographic key pairs...');
        const generated = await generateUserKeyPairs();
        await saveUserPrivateKeys(currentUser.id, generated);

        if (!hasEnc || !existingEncPriv) {
          await userApi.registerKey('encryption', 'RSA-OAEP-3072', generated.encryptionPublicJwk);
        }
        if (!hasSig || !existingEncPriv) {
          await userApi.registerKey('signing', 'ECDSA-P256', generated.signingPublicJwk);
        }

        const updatedKeys = await userApi.getMyKeys();
        setKeys(updatedKeys);
        console.log('[DropSafe Crypto] Key pairs registered successfully.');
      }
    } catch (err) {
      console.error('[DropSafe Crypto] Failed setting up user keys:', err);
    }
  };

  const refreshProfile = async () => {
    try {
      const profile = await userApi.getProfile();
      setUser(profile);
      await ensureKeysSetUp(profile);
    } catch {
      setUser(null);
      setKeys([]);
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      if (getAccessToken()) {
        await refreshProfile();
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email: string, pass: string) => {
    await authApi.login(email, pass);
    const profile = await userApi.getProfile();
    setUser(profile);
    await ensureKeysSetUp(profile);
  };

  const register = async (email: string, pass: string, name?: string) => {
    await authApi.register(email, pass, name);
    const profile = await userApi.getProfile();
    setUser(profile);
    await ensureKeysSetUp(profile);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.warn('Logout error ignored:', err);
    } finally {
      setUser(null);
      setKeys([]);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        keys,
        isAuthenticated: !!user,
        isLoading,
        activeEncryptionKeyId: activeEncryptionKey?.id || null,
        activeSigningKeyId: activeSigningKey?.id || null,
        login,
        register,
        logout,
        ensureKeysSetUp,
        initializeCryptoKeys: ensureKeysSetUp,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
