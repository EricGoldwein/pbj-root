/**
 * Build {{PROJECT_NAME}} Wrapped stats for a user from Ledger and Log data
 * 
 * Customize this file to match your data processing needs
 */

import type {
  LedgerRow,
  LogRow,
  {{PROJECT_NAME}}WrappedStats,
} from './wrappedTypes';
import { wrappedCopy } from './wrappedCopy';

/**
 * Parse date string in mm/dd/yy format to Date object
 * Handles both single and double-digit months/days
 * Customize date format parsing based on your data format
 */
function parseDate(dateStr: string): Date | null {
  if (!dateStr || !dateStr.trim()) return null;

  try {
    // Handle formats like "5/28/25", "05/28/25", "8-23-25", "8/23/25"
    // Customize this based on your date format
    const normalized = dateStr.trim().replace(/-/g, '/');
    const parts = normalized.split('/');
    
    if (parts.length !== 3) return null;

    const month = parseInt(parts[0], 10) - 1; // JS months are 0-indexed
    const day = parseInt(parts[1], 10);
    let year = parseInt(parts[2], 10);

    // Handle 2-digit years (assume 2000s)
    if (year < 100) {
      year += 2000;
    }

    if (isNaN(month) || isNaN(day) || isNaN(year)) return null;
    if (month < 0 || month > 11) return null;
    if (day < 1 || day > 31) return null;

    const date = new Date(year, month, day);
    if (isNaN(date.getTime())) return null;

    return date;
  } catch {
    return null;
  }
}

/**
 * Calculate median of an array of numbers
 */
function median(numbers: number[]): number | null {
  if (numbers.length === 0) return null;
  
  const sorted = [...numbers].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

/**
 * Group {{CATEGORY_1}} sessions by date and activity link
 * Customize this based on how you want to group activities
 */
interface {{CATEGORY_1}}Session {
  date: Date;
  {{METRIC_NAME_LOWERCASE}}: number;
  sourceType?: string | null;
  activityLink?: string | null;
}

function group{{CATEGORY_1}}Sessions(logRows: LogRow[]): {{CATEGORY_1}}Session[] {
  const sessions = new Map<string, {{CATEGORY_1}}Session>();

  for (const row of logRows) {
    // Customize category check based on your data
    if (row.{{CATEGORY_FIELD}} !== '{{CATEGORY_1}}' || row.{{AMOUNT_FIELD}} <= 0) continue;

    const date = parseDate(row.{{DATE_FIELD}});
    if (!date) continue;

    // Create session key: date + activity link (if present)
    // Customize grouping logic as needed
    const dateKey = date.toISOString().split('T')[0];
    const sessionKey = row.{{ACTIVITY_LINK_FIELD}}
      ? `${dateKey}:${row.{{ACTIVITY_LINK_FIELD}}}`
      : dateKey;

    if (sessions.has(sessionKey)) {
      const session = sessions.get(sessionKey)!;
      session.{{METRIC_NAME_LOWERCASE}} += row.{{AMOUNT_FIELD}};
      // Use first non-null source type
      if (!session.sourceType && row.{{SOURCE_TYPE_FIELD}}) {
        session.sourceType = row.{{SOURCE_TYPE_FIELD}};
      }
    } else {
      sessions.set(sessionKey, {
        date,
        {{METRIC_NAME_LOWERCASE}}: row.{{AMOUNT_FIELD}},
        sourceType: row.{{SOURCE_TYPE_FIELD}} || null,
        activityLink: row.{{ACTIVITY_LINK_FIELD}} || null,
      });
    }
  }

  return Array.from(sessions.values());
}

/**
 * Calculate {{TRUST_SCORE_NAME}} (0-100)
 * Customize this scoring algorithm based on your metrics
 */
function calculate{{TRUST_SCORE_NAME}}(
  hasInitiation: boolean,
  totalSessions: number,
  avg{{METRIC_NAME}}PerSession: number | null,
  {{MEMBERSHIP_FIELD}}Completed: boolean,
  total{{ACTIVITY_TYPE_1}}s: number,
  totalMined: number
): { score: number; label: string } {
  let score = 0;

  // Customize scoring logic based on your criteria
  // Example scoring:
  if (hasInitiation) score += 20;
  if (totalSessions >= 5) score += 20;
  if (avg{{METRIC_NAME}}PerSession !== null && avg{{METRIC_NAME}}PerSession >= 3 && avg{{METRIC_NAME}}PerSession <= 12) {
    score += 20;
  }
  if ({{MEMBERSHIP_FIELD}}Completed) score += 15;
  if (total{{ACTIVITY_TYPE_1}}s <= 5) score += 10;
  if (totalMined >= 80 && total{{ACTIVITY_TYPE_1}}s >= 5) {
    score -= 10;
  }

  // Clamp to [0, 100]
  score = Math.max(0, Math.min(100, score));

  // Determine label based on score
  // Customize labels based on your needs
  let label: string;
  if (score >= 80) {
    label = wrappedCopy.{{TRUST_SCORE_LABEL}}s.trusted;
  } else if (score >= 60) {
    label = wrappedCopy.{{TRUST_SCORE_LABEL}}s.mostlyReliable;
  } else if (score >= 40) {
    label = wrappedCopy.{{TRUST_SCORE_LABEL}}s.chaoticNeutral;
  } else {
    label = wrappedCopy.{{TRUST_SCORE_LABEL}}s.statisticalProblem;
  }

  return { score, label };
}

/**
 * Build wrapped stats for a user
 * This is the main function that processes all data
 */
export function buildWrappedStatsForUser(
  username: string,
  ledgerRows: LedgerRow[],
  logRows: LogRow[]
): {{PROJECT_NAME}}WrappedStats {
  // Find user's ledger row
  const ledgerRow = ledgerRows.find(
    (r) => r.{{USERNAME_FIELD}}.toLowerCase().trim() === username.toLowerCase().trim()
  );

  // Use the username from ledger row if available (preserves correct capitalization),
  // otherwise use the provided username
  const displayUsername = ledgerRow ? ledgerRow.{{USERNAME_FIELD}}.trim() : username.trim();

  // Filter log rows for this user
  const userLogRows = logRows.filter(
    (r) => r.{{USERNAME_FIELD}}.toLowerCase().trim() === username.toLowerCase().trim()
  );

  // Initiation Date
  // Customize based on your initiation logic
  let initiationDate: Date | null = null;
  const initiationRows = userLogRows.filter(
    (r) => r.{{INITIATION_FIELD}} === 'Yes'
  );
  
  if (initiationRows.length > 0) {
    const dates = initiationRows
      .map((r) => parseDate(r.{{DATE_FIELD}}))
      .filter((d): d is Date => d !== null)
      .sort((a, b) => a.getTime() - b.getTime());
    
    if (dates.length > 0) {
      initiationDate = dates[0];
    }
  } else {
    // Use earliest date across all categories
    const allDates = userLogRows
      .map((r) => parseDate(r.{{DATE_FIELD}}))
      .filter((d): d is Date => d !== null)
      .sort((a, b) => a.getTime() - b.getTime());
    
    if (allDates.length > 0) {
      initiationDate = allDates[0];
    }
  }

  // Total {{METRIC_NAME}}
  let total{{METRIC_NAME}} = 0;
  if (ledgerRow) {
    total{{METRIC_NAME}} = ledgerRow.{{TOTAL_METRIC_FIELD}} || 0;
  } else {
    // Fallback: sum {{CATEGORY_1}} rows with positive {{AMOUNT_FIELD}}
    total{{METRIC_NAME}} = userLogRows
      .filter((r) => r.{{CATEGORY_FIELD}} === '{{CATEGORY_1}}' && r.{{AMOUNT_FIELD}} > 0)
      .reduce((sum, r) => sum + r.{{AMOUNT_FIELD}}, 0);
  }

  // {{CATEGORY_1}} sessions
  const {{CATEGORY_1}}Rows = userLogRows.filter((r) => r.{{CATEGORY_FIELD}} === '{{CATEGORY_1}}');
  const sessions = group{{CATEGORY_1}}Sessions({{CATEGORY_1}}Rows);
  
  const session{{METRIC_NAME}}Values = sessions.map((s) => s.{{METRIC_NAME_LOWERCASE}});
  const totalSessions = sessions.length;
  const avg{{METRIC_NAME}}PerSession =
    session{{METRIC_NAME}}Values.length > 0
      ? session{{METRIC_NAME}}Values.reduce((a, b) => a + b, 0) / session{{METRIC_NAME}}Values.length
      : null;
  const median{{METRIC_NAME}}PerSession = median(session{{METRIC_NAME}}Values);

  // Highest {{METRIC_NAME}} Session
  const highestSession =
    sessions.length > 0
      ? sessions.reduce((max, s) => (s.{{METRIC_NAME_LOWERCASE}} > max.{{METRIC_NAME_LOWERCASE}} ? s : max), sessions[0])
      : null;

  // {{ACTIVITY_TYPE_1}}s
  const {{ACTIVITY_TYPE_1}}Rows = userLogRows.filter((r) => r.{{CATEGORY_FIELD}} === '{{ACTIVITY_TYPE_1}}');
  const total{{ACTIVITY_TYPE_1}}s = {{ACTIVITY_TYPE_1}}Rows.length;
  const net{{ACTIVITY_TYPE_1}}{{METRIC_NAME}} = {{ACTIVITY_TYPE_1}}Rows.reduce((sum, r) => sum + r.{{AMOUNT_FIELD}}, 0);

  // Last {{ACTIVITY_TYPE_1}} Date
  let last{{ACTIVITY_TYPE_1}}Date: Date | null = null;
  // Customize based on your ledger structure
  if ({{ACTIVITY_TYPE_1}}Rows.length > 0) {
    const {{ACTIVITY_TYPE_1}}Dates = {{ACTIVITY_TYPE_1}}Rows
      .map((r) => parseDate(r.{{DATE_FIELD}}))
      .filter((d): d is Date => d !== null)
      .sort((a, b) => b.getTime() - a.getTime());
    
    if ({{ACTIVITY_TYPE_1}}Dates.length > 0) {
      last{{ACTIVITY_TYPE_1}}Date = {{ACTIVITY_TYPE_1}}Dates[0];
    }
  }

  // Calculate {{ACHIEVEMENT_1}} amount
  // Customize based on your achievement system
  let {{ACHIEVEMENT_1}}Amount = 0;
  if (ledgerRow && ledgerRow.{{ACHIEVEMENT_FIELD_1}} > 0) {
    {{ACHIEVEMENT_1}}Amount = ledgerRow.{{ACHIEVEMENT_FIELD_1}};
  } else {
    {{ACHIEVEMENT_1}}Amount = userLogRows
      .filter((r) => r.{{CATEGORY_FIELD}} === '{{ACHIEVEMENT_1}}')
      .reduce((sum, r) => sum + (r.{{AMOUNT_FIELD}} || 0), 0);
  }
  
  const has{{ACHIEVEMENT_1}} = {{ACHIEVEMENT_1}}Amount > 0;
  
  // Other achievements
  const has{{ACHIEVEMENT_2}} = ledgerRow ? ledgerRow.{{ACHIEVEMENT_FIELD_2}} > 0 : false;
  const has{{ACHIEVEMENT_3}} = 
    (ledgerRow && ledgerRow.{{ACHIEVEMENT_FIELD_3}} > 0) ||
    userLogRows.some((r) => r.{{CATEGORY_FIELD}} === '{{ACHIEVEMENT_3}}');
  const has{{ACHIEVEMENT_4}} =
    (ledgerRow && ledgerRow.{{ACHIEVEMENT_FIELD_4}} > 0) ||
    userLogRows.some((r) => r.{{CATEGORY_FIELD}} === '{{ACHIEVEMENT_4}}');

  // {{MEMBERSHIP_FIELD}}
  const {{MEMBERSHIP_FIELD}}Completed =
    has{{ACHIEVEMENT_4}} || (ledgerRow ? ledgerRow.{{BALANCE_FIELD}} >= 10 : false);

  // {{TRUST_SCORE_NAME}}
  const { score: {{TRUST_SCORE_NAME}}, label: {{TRUST_SCORE_LABEL}} } =
    calculate{{TRUST_SCORE_NAME}}(
      initiationDate !== null,
      totalSessions,
      avg{{METRIC_NAME}}PerSession,
      {{MEMBERSHIP_FIELD}}Completed,
      total{{ACTIVITY_TYPE_1}}s,
      total{{METRIC_NAME}}
    );

  // {{SCORE_NAME}} (custom score, e.g., 3-digit random number, deterministic based on username)
  const usernameHash = displayUsername.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const {{SCORE_NAME}} = 100 + (usernameHash % 900); // Random number between 100-999

  // Get additional fields from ledger row
  const {{DISTANCE_FIELD}} = ledgerRow ? ledgerRow.{{DISTANCE_FIELD}} || undefined : undefined;
  const {{RANK_FIELD}} = ledgerRow ? ledgerRow.{{RANK_FIELD}} || undefined : undefined;
  const {{VOTING_SHARE_FIELD}} = ledgerRow && ledgerRow.{{VOTING_SHARE_FIELD}}
    ? parseFloat(String(ledgerRow.{{VOTING_SHARE_FIELD}})) || undefined
    : undefined;

  return {
    username: displayUsername,
    initiationDate,
    total{{METRIC_NAME}},
    highest{{METRIC_NAME}}Session: highestSession
      ? {
          date: highestSession.date,
          {{METRIC_NAME_LOWERCASE}}: highestSession.{{METRIC_NAME_LOWERCASE}},
          sourceType: highestSession.sourceType,
        }
      : null,
    totalSessions,
    avg{{METRIC_NAME}}PerSession,
    median{{METRIC_NAME}}PerSession,
    total{{ACTIVITY_TYPE_1}}s,
    net{{ACTIVITY_TYPE_1}}{{METRIC_NAME}},
    last{{ACTIVITY_TYPE_1}}Date,
    has{{ACHIEVEMENT_1}},
    {{ACHIEVEMENT_1}}Amount,
    has{{ACHIEVEMENT_2}},
    has{{ACHIEVEMENT_3}},
    has{{ACHIEVEMENT_4}},
    {{MEMBERSHIP_FIELD}}Completed,
    {{TRUST_SCORE_NAME}},
    {{TRUST_SCORE_LABEL}},
    {{SCORE_NAME}},
    {{DISTANCE_FIELD}},
    {{RANK_FIELD}},
    {{VOTING_SHARE_FIELD}},
  };
}

