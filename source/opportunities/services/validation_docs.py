from pathlib import Path

from django.core.exceptions import ValidationError

from opportunities.models import Validation, ValidationDocument, ValidationDocumentType
from utils.services import BaseService


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".pdf", ".png"}


class CreateValidationDocumentService(BaseService):
    def run(
        self,
        *,
        validation: Validation,
        document_type,
        document,
        uploaded_by=None,
        observations: str | None = None,
    ) -> ValidationDocument:
        if validation.state != Validation.State.PREPARING:
            raise ValidationError({
                "validation": "Documents can only be uploaded while the validation is preparing."
            })
        if not document:
            raise ValidationError({"document": "Please attach a document."})
        if isinstance(document_type, ValidationDocumentType):
            doc_type = document_type
        else:
            try:
                doc_type = ValidationDocumentType.objects.get(code=document_type)
            except ValidationDocumentType.DoesNotExist:
                raise ValidationError({"document_type": "Invalid document type."})
        # Enforce operation type compatibility
        op_type = validation.opportunity.source_intention.operation_type
        if doc_type.operation_type_id and doc_type.operation_type_id != op_type.id:
            raise ValidationError({"document_type": "Document type not allowed for this operation type."})
        suffix = Path(document.name or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed_display = ", ".join(ext.upper().lstrip(".") for ext in sorted(ALLOWED_EXTENSIONS))
            raise ValidationError({"document": f"Formato inválido. Usa archivos {allowed_display}."})

        return ValidationDocument.objects.create(
            validation=validation,
            document_type=doc_type,
            observations=observations or "",
            document=document,
            uploaded_by=uploaded_by,
        )


class ReviewValidationDocumentService(BaseService):
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


__all__ = [
    "CreateValidationDocumentService",
    "ReviewValidationDocumentService",
]
