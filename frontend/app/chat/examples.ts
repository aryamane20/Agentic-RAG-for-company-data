import type { Role } from "@/lib/backend";

export interface ExamplePrompt {
  doc: string;
  text: string;
}

export const ROLE_LABELS: Record<Role, string> = {
  engineer: "Engineer",
  hr_staff: "HR staff",
  executive: "Executive",
};

// Verified live against the real ingested corpus (not the design mockup's
// placeholder docs, several of which don't exist -- e.g. security_policy.md,
// eng_handbook.md, onboarding_checklist.md, q3_financials.md,
// headcount_plan.md, board_update.md). Every prompt below was tested end to
// end and confirmed to return a grounded, non-refusal answer for its role.
export const EXAMPLE_PROMPTS: Record<Role, ExamplePrompt[]> = {
  engineer: [
    { doc: "on_call_runbook.md", text: "What’s the on-call escalation process?" },
    { doc: "api_design_guidelines.md", text: "How are our list endpoints paginated?" },
    { doc: "employee_handbook.md", text: "How much PTO can I carry over?" },
    { doc: "system_architecture.md", text: "What service is the current scaling bottleneck?" },
  ],
  hr_staff: [
    { doc: "compensation_bands.md", text: "What’s the salary band for a Senior Software Engineer?" },
    { doc: "employee_handbook.md", text: "What’s our parental leave policy?" },
    { doc: "benefits_guide.md", text: "When does open enrollment run?" },
    { doc: "compensation_bands.md", text: "What’s the standard merit increase pool?" },
  ],
  executive: [
    { doc: "board_deck_excerpt.md", text: "How did Q1 ARR compare to plan?" },
    { doc: "annual_budget_summary.md", text: "How many net new hires does the FY2026 plan add for Engineering?" },
    { doc: "vendor_contract_summary.md", text: "What’s the AWS annual contract commitment?" },
    { doc: "board_deck_excerpt.md", text: "What risks were flagged to the board this quarter?" },
  ],
};
