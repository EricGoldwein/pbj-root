/**
 * Centralized text and copy for {{BRAND_NAME}}
 * 
 * Customize all text content here
 */

export const wrappedCopy = {
  title: {
    main: '{{BRAND_NAME}}',
    subtitle: '{{SUBTITLE_TEXT}}',
  },

  cards: {
    initiation: {
      title: '{{INITIATION_TITLE}}',
      honeymoon: "{{INITIATION_HONEYMOON_TEXT}}",
    },
    totalMetric: {
      title: '{{TOTAL_METRIC_TITLE}} ({{YEAR}})',
      distance: '{{DISTANCE_TEXT}}', // Use {km} placeholder for distance value
    },
    highestSession: {
      title: '{{HIGHEST_SESSION_TITLE}}',
    },
    {{METRIC_NAME_LOWERCASE}}PerSession: {
      title: '{{AVG_PER_SESSION_TITLE}}', // Use {avg} placeholder for average value
      steady: '{{STEADY_LABEL}}',
      spiky: '{{SPIKY_LABEL}}',
      emotionallyVariable: '{{EMOTIONALLY_VARIABLE_LABEL}}',
    },
    {{MEMBERSHIP_FIELD}}: {
      completed: '{{MEMBERSHIP_COMPLETED_TEXT}}',
      notCompleted: '{{MEMBERSHIP_NOT_COMPLETED_TEXT}}',
    },
    {{ACTIVITY_TYPE_1}}s: {
      no{{ACTIVITY_TYPE_1}}s: "{{NO_ACTIVITY_TEXT}}",
      has{{ACTIVITY_TYPE_1}}s: "{{HAS_ACTIVITY_TEXT}}", // Use {count} placeholder
      dashboard: "{{DASHBOARD_TITLE}}",
      {{ACTIVITY_TYPE_1}}sTitle: "{{ACTIVITY_TYPE_1}}S_TITLE",
    },
    specialUnlocks: {
      {{ACHIEVEMENT_1}}: '{{ACHIEVEMENT_1_LABEL}}',
      {{ACHIEVEMENT_2}}: '{{ACHIEVEMENT_2_LABEL}}',
      {{ACHIEVEMENT_3}}: '{{ACHIEVEMENT_3_LABEL}}',
    },
    {{TRUST_SCORE_NAME}}: {
      title: '{{TRUST_SCORE_TITLE}}',
      verdict: '{{TRUST_SCORE_VERDICT}}', // Use {label} placeholder
    },
    nextYear: {
      highMinedLowTrust: '{{NEXT_YEAR_HIGH_LOW_TEXT}}',
      moderateMinedHighTrust: '{{NEXT_YEAR_MODERATE_HIGH_TEXT}}',
    },
  },

  {{TRUST_SCORE_LABEL}}s: {
    trusted: '{{TRUSTED_LABEL}}',
    mostlyReliable: '{{MOSTLY_RELIABLE_LABEL}}',
    chaoticNeutral: '{{CHAOTIC_NEUTRAL_LABEL}}',
    statisticalProblem: '{{STATISTICAL_PROBLEM_LABEL}}',
  },
};

