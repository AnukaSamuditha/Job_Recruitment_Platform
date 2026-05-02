from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Job(_message.Message):
    __slots__ = ("id", "title", "company", "description_plain", "has_embedding")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    COMPANY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_PLAIN_FIELD_NUMBER: _ClassVar[int]
    HAS_EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    company: str
    description_plain: str
    has_embedding: bool
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., company: _Optional[str] = ..., description_plain: _Optional[str] = ..., has_embedding: bool = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ...) -> None: ...

class CandidateSummary(_message.Message):
    __slots__ = ("id", "display_name", "cv_storage_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    CV_STORAGE_KEY_FIELD_NUMBER: _ClassVar[int]
    id: str
    display_name: str
    cv_storage_key: str
    def __init__(self, id: _Optional[str] = ..., display_name: _Optional[str] = ..., cv_storage_key: _Optional[str] = ...) -> None: ...

class ListCandidatesRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class ListCandidatesResponse(_message.Message):
    __slots__ = ("candidates",)
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    candidates: _containers.RepeatedCompositeFieldContainer[CandidateSummary]
    def __init__(self, candidates: _Optional[_Iterable[_Union[CandidateSummary, _Mapping]]] = ...) -> None: ...

class ComputeCandidateJobFitRequest(_message.Message):
    __slots__ = ("job_id", "candidate_id")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    CANDIDATE_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    candidate_id: str
    def __init__(self, job_id: _Optional[str] = ..., candidate_id: _Optional[str] = ...) -> None: ...

class ComputeCandidateJobFitResponse(_message.Message):
    __slots__ = ("overall_score", "matched_skills", "missing_skills", "summary_line")
    OVERALL_SCORE_FIELD_NUMBER: _ClassVar[int]
    MATCHED_SKILLS_FIELD_NUMBER: _ClassVar[int]
    MISSING_SKILLS_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_LINE_FIELD_NUMBER: _ClassVar[int]
    overall_score: int
    matched_skills: _containers.RepeatedScalarFieldContainer[str]
    missing_skills: _containers.RepeatedScalarFieldContainer[str]
    summary_line: str
    def __init__(self, overall_score: _Optional[int] = ..., matched_skills: _Optional[_Iterable[str]] = ..., missing_skills: _Optional[_Iterable[str]] = ..., summary_line: _Optional[str] = ...) -> None: ...
