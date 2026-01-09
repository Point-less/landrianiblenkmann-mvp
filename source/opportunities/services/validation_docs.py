from pathlib import Path
from django.db import models
from django.core.exceptions import ValidationError

from opportunities.models import (
    Validation,
    ValidationAdditionalDocument,
    ValidationDocument,
    ValidationDocumentType,
)
from utils.services import BaseService
from utils.authorization import PROVIDER_OPPORTUNITY_PUBLISH

DEFAULT_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".pdf", ".png"}


class CreateValidationDocumentService(BaseService):
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(
        self,
        *,
        validation: Validation,
        document_type,
        document,
        uploaded_by=None,
        observations: str | None = None,
    ) -> ValidationDocument:
        if validation.state not in {Validation.State.PREPARING, Validation.State.PRESENTED}:
            raise ValidationError(
                {
                    "validation": "Documents can only be uploaded while the validation is preparing or awaiting approval."
                }
            )
        if not document:
            raise ValidationError({"document": "Please attach a document."})
        if isinstance(document_type, ValidationDocumentType):
            doc_type = document_type
        else:
            try:
                doc_type = ValidationDocumentType.objects.get(code=document_type)
            except ValidationDocumentType.DoesNotExist:
                raise ValidationError({"document_type": "Invalid document type."})
        # Only required document types are allowed (optional types are handled via custom uploads)
        if not doc_type.required:
            raise ValidationError(
                {"document_type": "Only required document types can be uploaded here. Use custom documents for extras."}
            )
        # Enforce operation type compatibility
        op_type = validation.opportunity.source_intention.operation_type
        if doc_type.operation_type_id and doc_type.operation_type_id != op_type.id:
            raise ValidationError({"document_type": "Document type not allowed for this operation type."})
        suffix = Path(document.name or "").suffix.lower()
        allowed_exts = {("." + ext.lower().lstrip(".")) for ext in (doc_type.accepted_formats or []) if ext}
        if not allowed_exts:
            raise ValidationError({"document_type": "Configure accepted formats for this document type before uploading."})
        if suffix not in allowed_exts:
            allowed_display = ", ".join(ext.upper().lstrip(".") for ext in sorted(allowed_exts))
            raise ValidationError({"document": f"Invalid format. Allowed files: {allowed_display}."})

        return ValidationDocument.objects.create(
            validation=validation,
            document_type=doc_type,
            observations=observations or "",
            document=document,
            uploaded_by=uploaded_by,
        )


class ReviewValidationDocumentService(BaseService):
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(self, *, document: ValidationDocument, action: str, reviewer, comment: str | None = None) -> ValidationDocument:
        if action not in {"accept", "reject"}:
            raise ValidationError({"action": "Invalid review action."})
        if reviewer is None:
            raise ValidationError({"reviewer": "Reviewer is required."})
        if document.validation.state != Validation.State.PRESENTED:
            raise ValidationError({"document": "Documents can only be reviewed once the validation is presented."})

        if action == "accept":
            document.accept(reviewer=reviewer, comment=comment)
        else:
            document.reject(reviewer=reviewer, comment=comment)
        document.save(update_fields=["status", "reviewer_comment", "decided_by", "decided_at", "updated_at"])
        return document


class CreateAdditionalValidationDocumentService(BaseService):
    required_action = PROVIDER_OPPORTUNITY_PUBLISH

    def run(
        self,
        *,
        validation: Validation,
        document,
        uploaded_by=None,
        observations: str | None = None,
    ) -> ValidationAdditionalDocument:
        if validation.state not in {Validation.State.PREPARING, Validation.State.PRESENTED}:
            raise ValidationError(
                {
                    "validation": "Custom documents can only be uploaded while the validation is preparing or awaiting approval."
                }
            )
        if not document:
            raise ValidationError({"document": "Please attach a document."})

        return ValidationAdditionalDocument.objects.create(
            validation=validation,
            observations=observations or "",
            document=document,
            uploaded_by=uploaded_by,
        )


class AllowedValidationDocumentTypesQuery(BaseService):
    """Compute allowed validation document types for a validation instance."""

    atomic = False

    def run(self, *, validation=None, required_only: bool = True, operation_type=None):
        if validation:
            qs = validation.required_document_types()
            op_type = validation.opportunity.source_intention.operation_type
        else:
            qs = ValidationDocumentType.objects.filter(required=True) if required_only else ValidationDocumentType.objects.all()
            op_type = operation_type

        if op_type:
            qs = qs.filter(models.Q(operation_type__isnull=True) | models.Q(operation_type=op_type))
        return qs.distinct()


__all__ = [
    "CreateValidationDocumentService",
    "ReviewValidationDocumentService",
    "CreateAdditionalValidationDocumentService",
    "AllowedValidationDocumentTypesQuery",
]
