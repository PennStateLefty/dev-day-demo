export interface Claim {
  claimId: string;
  policyId?: string;
  lossDate?: string;
  claimantStatement?: string;
  repairEstimate?: { amount: number; currency: string };
}

export type CheckStatus = "not_run" | "running" | "complete" | "failed";

export interface Artifact {
  artifactId: string;
  artifactType: string;
  description?: string;
}

export interface ImageAnalysis {
  status: "completed" | "no_evidence" | "unavailable";
  artifactIds: string[];
  model?: string;
  modelVersion?: string;
  inputSha256?: string;
  limitation?: string;
  observations?: {
    visibility: "clear" | "limited" | "unusable";
    parts: { part: string; damage: string; severity: string }[];
    statementComparison: string;
    limitations: string[];
  };
}

export interface Recommendation {
  summary: string;
  triageRecommendation: "request_information" | "human_review" | "escalate";
  recommendedActions: string[];
  humanReviewRequired: true;
}

export interface Finding {
  findingCode: string;
  status: "clear" | "missing" | "inconsistent" | "needs_review" | "unknown";
  description: string;
}

export interface Citation {
  citationId: string;
  sourceDocument: string;
  section: string;
  quotedText: string;
}

export interface Assessment {
  assessmentId: string;
  claimId: string;
  summary: string;
  completenessFindings: Finding[];
  policyCitations: Citation[];
  policyBasis: "grounded" | "unavailable" | "not_assessed";
  triageRecommendation: string;
  humanReviewRequired: true;
  imageAnalysis?: ImageAnalysis;
}

export interface ResponseDraft {
  body: string;
  humanReviewRequired: true;
}

export interface CommunicationRecord {
  communicationId: string;
  claimId: string;
  assessmentId: string;
  citationIds: string[];
  artifactIds: string[];
  body: string;
  createdAt: string;
  reviewedBy: string | null;
  reviewedAt: string | null;
  sentAt: string | null;
  humanReviewRequired: true;
}

export interface WorkflowResult {
  assessment: Assessment;
  responseDraft?: ResponseDraft;
  recommendation?: Recommendation;
  agentName?: string;
  agentVersion?: string;
}

export interface CommunicationRunResult {
  assessment: Assessment;
  recommendation?: Recommendation | null;
  communication: CommunicationRecord;
  agentName?: string | null;
  agentVersion?: string | null;
}
