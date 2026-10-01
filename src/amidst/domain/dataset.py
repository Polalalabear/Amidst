"""Provider-neutral raw-frame dataset; benchmark references live separately."""

from typing import Literal

from amidst.domain.common import DomainModel
from amidst.domain.stream import RawProjectedFrameSample


class FrameSampleDataset(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    samples: tuple[RawProjectedFrameSample, ...]
