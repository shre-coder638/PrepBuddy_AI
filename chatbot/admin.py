"""Controlled administration of ANN learning experiences."""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from accounts.permissions import get_authorized_staff_profile

from chatbot.models import ANNExperience, ANNReviewedExample

from chatbot.ann.experience_service import (
    submit_review_example,
    review_example,
)


def _allowed(user, *permissions):

    if not (
        user.is_authenticated
        and user.is_active
        and user.is_staff
    ):
        return False

    profile = get_authorized_staff_profile(user)

    return (
        profile is not None
        and profile.role == "doctor"
        and all(
            user.has_perm(permission)
            for permission in permissions
        )
    )


class SubmitExampleForm(forms.Form):

    question = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=(
            "Enter a manually de-identified question. "
            "Do not include names, contact details, "
            "record identifiers or other personal information."
        ),
    )

    language = forms.ChoiceField(
        choices=ANNReviewedExample.Language.choices,
    )

    step_id = forms.IntegerField(min_value=1)

    deidentified = forms.BooleanField(
        required=True,
        label="I confirm that personal identifiers have been removed.",
    )


class ReviewExampleForm(forms.Form):

    decision = forms.ChoiceField(
        choices=[
            ("", "Select a decision"),
            ("approve", "Approve training example"),
            ("reject", "Reject training example"),
        ],
    )

    relevance_label = forms.ChoiceField(
        choices=[
            ("", "Select relevance label"),
            *ANNReviewedExample.Relevance.choices,
        ],
        required=False,
    )

    escalation = forms.ChoiceField(
        choices=[
            ("", "Select escalation decision"),
            ("yes", "Requires clinical escalation"),
            ("no", "No additional escalation identified"),
        ],
        required=False,
    )

    def clean(self):

        cleaned = super().clean()

        if cleaned.get("decision") == "approve":

            if not cleaned.get("relevance_label"):
                self.add_error(
                    "relevance_label",
                    "A relevance label is required.",
                )

            if cleaned.get("escalation") not in {"yes", "no"}:
                self.add_error(
                    "escalation",
                    "An explicit decision is required.",
                )

        return cleaned


class ReadOnlyLearningAdmin(admin.ModelAdmin):

    actions = None

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_view_permission(self, request, obj=None):

        permission = (
            f"chatbot.view_{self.model._meta.model_name}"
        )

        return _allowed(request.user, permission)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):

        return tuple(
            field.name
            for field in self.model._meta.fields
        )

    def render_learning_form(
        self,
        request,
        *,
        title,
        form,
        example=None,
        experience=None,
    ):

        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "form": form,
            "opts": self.model._meta,
            "example": example,
            "experience": experience,
        }

        return TemplateResponse(
            request,
            "admin/ann_learning_form.html",
            context,
        )


@admin.register(ANNExperience)
class ANNExperienceAdmin(ReadOnlyLearningAdmin):

    list_display = (
        "id",
        "protocol_id",
        "outcome",
        "model_version",
        "needs_clinical_team",
        "latency_ms",
        "created_at",
        "submit_link",
    )

    list_filter = (
        "outcome",
        "protocol_id",
        "model_version",
        "needs_clinical_team",
    )

    @admin.display(description="Learning example")
    def submit_link(self, obj):

        if obj.protocol_id is None:
            return "-"

        return format_html(
            '<a href="{}">Submit example</a>',
            reverse(
                "admin:ann_submit_example",
                args=[obj.pk],
            ),
        )

    def get_urls(self):

        return [
            path(
                "<uuid:experience_id>/submit-example/",
                self.admin_site.admin_view(
                    self.submit_example_view
                ),
                name="ann_submit_example",
            ),
        ] + super().get_urls()

    def submit_example_view(self, request, experience_id):

        if not _allowed(
            request.user,
            "chatbot.view_annexperience",
            "chatbot.view_annreviewedexample",
            "chatbot.add_annreviewedexample",
        ):
            raise PermissionDenied

        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])

        experience = get_object_or_404(
            ANNExperience,
            pk=experience_id,
        )

        form = SubmitExampleForm(
            request.POST if request.method == "POST" else None
        )

        if request.method == "POST" and form.is_valid():

            try:

                example = submit_review_example(
                    user=request.user,
                    experience_id=experience.pk,
                    **form.cleaned_data,
                )

            except ValidationError:

                form.add_error(
                    None,
                    "Submission failed. Verify the protocol, "
                    "step ID and existing review examples.",
                )

            else:

                messages.success(
                    request,
                    "Pending learning example created.",
                )

                return redirect(
                    "admin:chatbot_annreviewedexample_change",
                    example.pk,
                )

        return self.render_learning_form(
            request,
            title="Submit de-identified ANN example",
            form=form,
            experience=experience,
        )


@admin.register(ANNReviewedExample)
class ANNReviewedExampleAdmin(ReadOnlyLearningAdmin):

    list_display = (
        "id",
        "protocol_id",
        "step_id",
        "language",
        "review_status",
        "relevance_label",
        "reviewed_at",
        "review_link",
    )

    list_filter = (
        "review_status",
        "language",
        "protocol_id",
        "relevance_label",
    )

    @admin.display(description="Review")
    def review_link(self, obj):

        if obj.review_status != "pending":
            return "-"

        return format_html(
            '<a href="{}">Review example</a>',
            reverse(
                "admin:ann_review_example",
                args=[obj.pk],
            ),
        )

    def get_urls(self):

        return [
            path(
                "<uuid:example_id>/review/",
                self.admin_site.admin_view(
                    self.review_example_view
                ),
                name="ann_review_example",
            ),
        ] + super().get_urls()

    def review_example_view(self, request, example_id):

        if not _allowed(
            request.user,
            "chatbot.view_annreviewedexample",
            "chatbot.change_annreviewedexample",
        ):
            raise PermissionDenied

        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])

        example = get_object_or_404(
            ANNReviewedExample,
            pk=example_id,
        )

        if example.review_status != "pending":
            messages.warning(
                request,
                "This example has already been reviewed.",
            )
            return redirect(
                "admin:chatbot_annreviewedexample_change",
                example.pk,
            )

        form = ReviewExampleForm(
            request.POST if request.method == "POST" else None
        )

        if request.method == "POST" and form.is_valid():

            data = form.cleaned_data

            approve = data["decision"] == "approve"

            try:

                review_example(
                    user=request.user,
                    example_id=example.pk,
                    approve=approve,
                    relevance_label=(
                        data["relevance_label"]
                        if approve else None
                    ),
                    requires_escalation=(
                        data["escalation"] == "yes"
                        if approve else None
                    ),
                )

            except ValidationError:

                form.add_error(
                    None,
                    "Review failed. The instruction may have "
                    "changed or the example is no longer pending.",
                )

            else:

                messages.success(
                    request,
                    "Review decision recorded.",
                )

                return redirect(
                    "admin:chatbot_annreviewedexample_change",
                    example.pk,
                )

        return self.render_learning_form(
            request,
            title="Review ANN training example",
            form=form,
            example=example,
        )
