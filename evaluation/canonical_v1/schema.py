"""Typed source and generated-manifest contracts for canonical_v1."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskType = Literal["short_text", "long_text", "choice", "numeric"]
ResponseType = Literal["line", "box", "checkbox"]
ResponseSafety = Literal["safe_physical"]


class CanonicalResponseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: str
    response_type: ResponseType
    response_safety: ResponseSafety = "safe_physical"
    label: str = "Answer:"
    height: float = Field(default=22, gt=0)


class CanonicalChoiceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1)


class CanonicalTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    order: int = Field(ge=1)
    prompt: str = Field(min_length=1)
    task_type: TaskType
    choices: list[CanonicalChoiceSpec] = Field(default_factory=list)
    responses: list[CanonicalResponseSpec] = Field(min_length=1)
    page_break_before: bool = False

    @model_validator(mode="after")
    def validate_choice_shape(self):
        checkbox_ids = [item.response_id for item in self.responses if item.response_type == "checkbox"]
        if self.task_type == "choice":
            if [item.value for item in self.choices] != ["A", "B", "C", "D"]:
                raise ValueError("choice tasks require ordered A/B/C/D choices")
            if len(checkbox_ids) != 4:
                raise ValueError("choice tasks require four checkbox responses")
        elif self.choices or checkbox_ids:
            raise ValueError("only choice tasks may define choices or checkbox responses")
        return self


class CanonicalDocumentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    sample_name: str
    title: str
    topic_label: str
    instructions: str
    context_title: str | None = None
    context: list[str] = Field(default_factory=list)
    tasks: list[CanonicalTaskSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_task_identity(self):
        if len(self.tasks) != 5:
            raise ValueError("canonical_v1 documents must contain exactly five tasks")
        if [task.order for task in self.tasks] != list(range(1, 6)):
            raise ValueError("canonical task order must be 1..5")
        ids = [task.task_id for task in self.tasks]
        response_ids = [response.response_id for task in self.tasks for response in task.responses]
        if len(ids) != len(set(ids)) or len(response_ids) != len(set(response_ids)):
            raise ValueError("task and response IDs must be unique within a document")
        return self


class CanonicalSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    documents: list[CanonicalDocumentSpec] = Field(min_length=3, max_length=3)


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str
    page_index: int = Field(ge=0)
    bbox_points: list[float] = Field(min_length=4, max_length=4)
    bbox_normalized: dict[str, float]


class GeneratedResponse(Region):
    response_type: ResponseType
    response_safety: ResponseSafety = "safe_physical"
    choice_value: str | None = None


class PromptToResponseRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: Literal["prompt_to_response_region"]
    from_region_id: str
    to_region_id: str


class GeneratedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    order: int
    task_type: TaskType
    prompt_text: str
    prompt_region: Region
    response_regions: list[GeneratedResponse]
    relations: list[PromptToResponseRelation]


class GeneratedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int
    width_points: float
    height_points: float
    page_role: Literal["student_worksheet"]
    tasks: list[GeneratedTask]


class GeneratedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    sample_name: str
    title: str
    pdf: str
    pdf_sha256: str
    pages: list[GeneratedPage]


class CanonicalManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    suite: Literal["canonical_v1"]
    coordinate_system: Literal["PDF points, top-left origin, [x0, y0, x1, y1]"]
    expected_labels_kind: Literal["deterministic_first_party"]
    machine_predictions_are_expected_labels: Literal[False]
    documents: list[GeneratedDocument]
