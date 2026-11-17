// Data models for future ABAC access policy management

export type PolicyIntent = 'allow' | 'deny';

export type PermittedAction = 'view' | 'download' | 'edit' | 'share';

export type ConditionOperator = 'equals' | 'not_equals';

export type SubjectAttribute = 'department' | 'role' | 'email_domain';

export type ResourceAttribute = 'file_type' | 'file_extension' | 'sensitivity_label';

export interface PolicyCondition {
  id: string;
  attribute: string;
  operator: ConditionOperator;
  value: string;
}

export interface AccessPolicyRecord {
  id: string;
  name: string;
  description?: string;
  intent: PolicyIntent;
  subjectConditions: PolicyCondition[];
  resourceConditions: PolicyCondition[];
  permittedAction: PermittedAction;
  requireApprovedNetwork?: boolean;
  createdAt: string;
}
