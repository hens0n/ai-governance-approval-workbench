from enum import Enum


class UserRole(str, Enum):
    requestor = "requestor"
    security_reviewer = "security_reviewer"
    privacy_reviewer = "privacy_reviewer"
    ao = "ao"
    ciso = "ciso"
    auditor = "auditor"


class UseCaseStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    triage = "triage"
    revision_requested = "revision_requested"
    in_review = "in_review"
    ao_decision = "ao_decision"
    approved = "approved"
    conditionally_approved = "conditionally_approved"
    rejected = "rejected"
    re_review_required = "re_review_required"
    revoked = "revoked"
    withdrawn = "withdrawn"


class RiskTier(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class Classification(str, Enum):
    public = "public"
    internal = "internal"
    sensitive = "sensitive"
    cui = "cui"


class ReviewRole(str, Enum):
    security = "security"
    privacy = "privacy"


class ReviewDecision(str, Enum):
    concur = "concur"
    non_concur = "non_concur"
    conditional = "conditional"


class ConditionStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    satisfied = "satisfied"
    waived = "waived"


class AttachmentKind(str, Enum):
    architecture = "architecture"
    dpia = "dpia"
    vendor_contract = "vendor_contract"
    model_card = "model_card"
    evidence = "evidence"
    other = "other"


class ControlFramework(str, Enum):
    nist_ai_rmf = "nist_ai_rmf"
    nist_800_53 = "nist_800_53"


class ControlAssignmentStatus(str, Enum):
    required = "required"
    evidenced = "evidenced"
    waived = "waived"


class ReReviewTrigger(str, Enum):
    scheduled = "scheduled"
    material_change = "material_change"
    policy_change = "policy_change"
