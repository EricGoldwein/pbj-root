/**
 * Type definitions for {{PROJECT_NAME}} Wrapped feature
 * 
 * Customize these interfaces to match your data structure
 */

export interface LedgerRow {
  {{USERNAME_FIELD}}: string;
  {{TOTAL_METRIC_FIELD}}: number;
  {{DISTANCE_FIELD}}?: number;
  {{RANK_FIELD}}?: number;
  {{BALANCE_FIELD}}?: number;
  {{DATE_FIELD}}?: string;
  {{ACHIEVEMENT_FIELD_1}}?: number;
  {{ACHIEVEMENT_FIELD_2}}?: number;
  // Add more fields as needed
}

export type LogCategory =
  | '{{CATEGORY_1}}'
  | '{{CATEGORY_2}}'
  | '{{CATEGORY_3}}'
  | string; // future categories

export interface LogRow {
  ID?: number;
  {{USERNAME_FIELD}}: string;
  {{DATE_FIELD}}: string; // mm/dd/yy or similar
  {{AMOUNT_FIELD}}: number;
  {{DISTANCE_FIELD}}?: number | null;
  {{ACTIVITY_LINK_FIELD}}?: string | null;
  {{SOURCE_TYPE_FIELD}}?: string | null;
  {{INITIATION_FIELD}}?: 'Yes' | 'No' | '' | null;
  {{NOTES_FIELD}}?: string | null;
  {{CATEGORY_FIELD}}: LogCategory;
  // Add more fields as needed
}

export interface {{PROJECT_NAME}}WrappedStats {
  username: string;

  initiationDate: Date | null;
  total{{METRIC_NAME}}: number;

  highest{{METRIC_NAME}}Session: {
    date: Date;
    {{METRIC_NAME_LOWERCASE}}: number;
    sourceType?: string | null;
  } | null;

  totalSessions: number;
  avg{{METRIC_NAME}}PerSession: number | null;
  median{{METRIC_NAME}}PerSession: number | null;

  total{{ACTIVITY_TYPE_1}}s: number;
  net{{ACTIVITY_TYPE_1}}{{METRIC_NAME}}: number;
  last{{ACTIVITY_TYPE_1}}Date: Date | null;

  has{{ACHIEVEMENT_1}}: boolean;
  {{ACHIEVEMENT_1}}Amount: number;
  {{ACHIEVEMENT_1}}Rank?: number;
  has{{ACHIEVEMENT_2}}: boolean;
  has{{ACHIEVEMENT_3}}: boolean;
  has{{ACHIEVEMENT_4}}: boolean;

  {{MEMBERSHIP_FIELD}}Completed: boolean;

  {{TRUST_SCORE_NAME}}: number; // 0–100
  {{TRUST_SCORE_LABEL}}: string;
  {{SCORE_NAME}}: number; // Custom score (e.g., 100-999)
  
  {{DISTANCE_FIELD}}?: number;
  {{RANK_FIELD}}?: number;
  {{VOTING_SHARE_FIELD}}?: number;
}

