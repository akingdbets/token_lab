"""공식 LLMLingua-2 모델을 사용하는 문맥 압축기.

모델은 첫 압축 때 지연 로드하고, 같은 모델/revision/device를 쓰는 보존 비율 변형끼리
공유한다. 로컬 토큰 분류 추론이므로 CompressResult의 LLM API 토큰에는 더하지 않는다.
단계별 입력·출력 통계는 이후 Streamlit/Grafana에서 재사용할 수 있게 info.trace에 남긴다.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from typing import Any

from compressors.base import Compressor

# 기술 QA에서 의미를 뒤집는 부정어와 식별자 구분 기호를 기본 보호한다.
DEFAULT_FORCE_TOKENS = (
    "\n",
    "?",
    "## Document:",
    "```",
    "_",
    "not",
    "no",
    "never",
    "without",
    "unless",
    "don't",
    "doesn't",
    "isn't",
    "aren't",
    "won't",
    "can't",
    "cannot",
    "default",
    "defaults",
    "except",
    "only",
)
TRACE_SCHEMA_VERSION = 1
SAFETY_POLICY_VERSION = (
    "question-identifiers-v1+fenced-code-blocks-v1+document-headers-v1+unsplit-identifiers-v1"
)
REJOIN_POLICY = "rejoin-punctuated-v2"
_LABEL_WORD_SEP = "\t\t|\t\t"   # llmlingua 0.2.2 return_word_label 의 기본 word_sep

_ENGINE_CACHE: dict[tuple[str, str, str], Any] = {}
_ENGINE_LOCK = threading.Lock()
_TECHNICAL_IDENTIFIER = re.compile(
    r"\b(?:[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*)\b"
)
_FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_DOCUMENT_HEADER = re.compile(r"^## Document:[^\n]*\n?", re.MULTILINE)
# 점·하이픈으로 이어진 영숫자 묶음: 버전 번호(0.95.0), 하이픈 이름(starlette-graphene3), 점 이름(pydantic.v1)
_PUNCTUATED_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_.-])[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)+(?![A-Za-z0-9_]|[.-][A-Za-z0-9])"
)


def _load_engine(model_name: str, model_revision: str, device: str):
    """같은 프로세스의 LLMLingua-2 변형이 모델 하나를 공유한다."""
    key = (model_name, model_revision, device)
    with _ENGINE_LOCK:
        if key not in _ENGINE_CACHE:
            from llmlingua import PromptCompressor

            _ENGINE_CACHE[key] = PromptCompressor(
                model_name=model_name,
                device_map=device,
                model_config={
                    "revision": model_revision,
                    "trust_remote_code": False,
                },
                use_llmlingua2=True,
            )
        return _ENGINE_CACHE[key]


def _short_error(exc: Exception) -> str:
    """전체 문맥이나 비밀값이 로그에 섞이지 않도록 한 줄·300자로 제한한다."""
    message = re.sub(r"\s+", " ", str(exc)).strip()
    return message[:300] or exc.__class__.__name__


def _fence_counts(text: str) -> tuple[int, int]:
    return text.count("```"), text.count("~~~")


def _split_fenced_blocks(text: str) -> list[tuple[bool, str]]:
    """본문을 원문 그대로 prose와 fenced code block으로 나눈다."""
    parts: list[tuple[bool, str]] = []
    buffer: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        match = _FENCE_LINE.match(line)
        if fence is None and match:
            if buffer:
                parts.append((False, "".join(buffer)))
            buffer = [line]
            fence = match.group(1)
        elif (
            fence is not None
            and match
            and match.group(1)[0] == fence[0]
            and len(match.group(1)) >= len(fence)
            and not line[match.end():].strip()
        ):
            buffer.append(line)
            parts.append((True, "".join(buffer)))
            buffer = []
            fence = None
        else:
            buffer.append(line)
    if buffer:
        parts.append((fence is not None, "".join(buffer)))
    return parts


def _unique_marker(name: str, index: int, text: str) -> str:
    marker = f"__LLMLINGUA_PROTECTED_{name}_{index:04d}__"
    while marker in text:
        marker = f"_{marker}_"
    return marker


def _mask_protected_units(
    text: str,
) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """코드 블록과 문서 경계 줄을 강제 보존할 고유 마커로 바꾼다.

    문서 경계 줄("## Document: ...")을 force token 으로만 두면, BERT tokenizer 가 남긴 단어를
    이어 붙이면서 " ##" 를 지워 두 번째 문서부터 "Document:" 만 남는다. 그래서 줄째로 빼 둔다.
    반환: (마커로 바꾼 본문, 등장 순서대로 모든 마커, 코드 블록 마커, 문서 경계 줄 마커)
    """
    masked: list[str] = []
    units: list[tuple[str, str]] = []
    code_blocks: list[tuple[str, str]] = []
    document_headers: list[tuple[str, str]] = []
    for is_code, chunk in _split_fenced_blocks(text):
        if is_code:
            marker = _unique_marker("CODE_BLOCK", len(code_blocks), text)
            code_blocks.append((marker, chunk))
            units.append((marker, chunk))
            masked.append(marker)
            continue
        cursor = 0
        for match in _DOCUMENT_HEADER.finditer(chunk):
            marker = _unique_marker("DOCUMENT_HEADER", len(document_headers), text)
            document_headers.append((marker, match.group(0)))
            units.append((marker, match.group(0)))
            masked.extend((chunk[cursor:match.start()], marker))
            cursor = match.end()
        masked.append(chunk[cursor:])
    return "".join(masked), units, code_blocks, document_headers


def _restore_protected_units(text: str, units: list[tuple[str, str]]) -> str:
    """모델이 마커 주변에 넣은 공백을 제거하고 코드 블록·문서 경계 줄을 원래 줄 단위로 복원한다."""
    restored: list[str] = []
    cursor = 0
    for marker, block in units:
        position = text.index(marker, cursor)
        prose = text[cursor:position].rstrip(" \t")
        if prose and not prose.endswith(("\n", "\r")):
            prose += "\n"
        restored.extend((prose, block))
        cursor = position + len(marker)
        if _DOCUMENT_HEADER.match(block):
            # 경계 줄은 줄바꿈까지 복원했으므로 다음 줄 앞에 모델이 넣은 공백은 버린다
            while cursor < len(text) and text[cursor] in " \t":
                cursor += 1
    restored.append(text[cursor:])
    return "".join(restored)


def _protected_identifiers(text: str, limit: int) -> list[str]:
    """snake_case/CamelCase 식별자를 등장 순서대로 중복 없이 고른다."""
    found = []
    seen = set()
    for match in _TECHNICAL_IDENTIFIER.finditer(text):
        value = match.group(0)
        if value not in seen and len(value) <= 128:
            found.append(value)
            seen.add(value)
            if len(found) >= limit:
                break
    return found


def _question_identifiers(question: str, context: str) -> list[str]:
    """질문과 문맥에 모두 있는 기술 식별자를 등장 순서대로 고른다."""
    found = []
    seen = set()
    for value in _protected_identifiers(question, limit=100):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])"
        if value not in seen and re.search(pattern, context):
            found.append(value)
            seen.add(value)
    return found


def _longest_first(tokens) -> list[str]:
    """force token 을 긴 것부터 둔다 (길이가 같으면 원래 순서). 짧은 토큰이 긴 토큰 안에서 먼저 치환되지 않게."""
    return sorted(tokens, key=len, reverse=True)


def _unsplittable_identifiers(text: str, identifiers: list[str], already: list[str], slots: int) -> list[str]:
    """식별자를 품은 더 긴 단어까지 함께 보호해, slots 안에서 쪼개지지 않는 식별자 목록을 고른다.

    llmlingua 0.2.2 는 여러 WordPiece 로 쪼개지는 force token 을 단어 경계 없이 str.replace 로 [NEWi] 로
    바꾼다. 그래서 "JWT" 를 보호하면 "PyJWT" 가 "Py[NEWi]" 로 잘려 복원 뒤 "Py JWT" 가 된다. 긴 것부터
    치환하면(_longest_first) 긴 단어도 보호 목록에 있을 때는 막히므로, 식별자를 품은 단어(영숫자·_ 연속)를
    함께 넣는다. 함께 넣을 자리가 없으면 그 식별자는 뺀다. already(마커 등)는 이미 보호되는 것으로 본다.
    """
    runs = set(re.findall(r"[A-Za-z0-9_]+", text))
    chosen = list(already)

    def needed(value: str, seen: set[str]) -> list[str]:
        out = [value]
        for run in runs:
            if value in run and run != value and run not in seen:
                seen.add(run)
                out.extend(needed(run, seen))
        return out

    picked = []
    for value in identifiers:
        add = [v for v in dict.fromkeys(needed(value, {value})) if v not in chosen]
        if len(picked) + len(add) > slots:
            continue
        chosen.extend(add)
        picked.extend(add)
    return picked


def _parse_word_labels(labeled: str) -> list[tuple[str, bool]]:
    """llmlingua 의 fn_labeled_original_prompt ("단어 라벨" 을 _LABEL_WORD_SEP 로 이음) 를 (단어, 남김) 목록으로."""
    pairs = []
    for item in labeled.split(_LABEL_WORD_SEP):
        word, _, label = item.rpartition(" ")
        if label not in ("0", "1"):
            raise ValueError(f"단어 라벨을 읽을 수 없습니다: {item[:40]!r}")
        pairs.append((word, label == "1"))
    return pairs


def _align_words(text: str, words: list[str]) -> list[tuple[int, int]] | None:
    """단어들을 text 에서 왼쪽부터 차례로 찾아 (시작, 끝) 위치를 돌려준다.

    LLMLingua-2 는 단어를 지우기만 하고 순서를 바꾸지 않으므로 원문과 압축 결과 모두에 이렇게 맞출 수 있다.
    단어 사이에서는 ASCII 영숫자가 아닌 글자만 건너뛴다: BERT 어휘에 없는 글자("—", "`" 등)는 [UNK] 가 되고,
    llmlingua 는 [UNK] 를 special token 으로 보고 단어 목록에서 뺀다 (ASCII 영숫자 한 글자는 늘 어휘에 있다).
    공백 단어("\\n" force token)는 압축 결과 끝에서 strip 될 수 있어 바로 앞 공백 안에 없으면 길이 0 으로 둔다.
    맞지 않는 단어가 있으면 None.
    """
    spans = []
    cursor = 0
    for word in words:
        pos = cursor
        while (
            pos < len(text)
            and (text[pos].isspace() or (word.strip() and not (text[pos].isascii() and text[pos].isalnum())))
            and not text.startswith(word, pos)
        ):
            pos += 1
        if text.startswith(word, pos):
            spans.append((pos, pos + len(word)))
            cursor = pos + len(word)
        elif not word.strip():
            spans.append((cursor, cursor))
        else:
            return None
    return spans


def _rejoin_punctuated(compressed: str, source: str, labeled: str) -> tuple[str, list[str], str | None]:
    """압축이 쪼갠 점·하이픈 묶음을 LLMLingua-2 의 단어별 남김 라벨로 원문 표기로 되돌린다.

    LLMLingua-2(BERT)는 "." "-" 를 따로 된 단어로 보고 지우며, force_reserve_digit 으로 숫자만 남겨
    "0.95.0" 이 "0 95 0" 이 된다. 라벨로 원문 단어마다 남았는지와 압축 결과 속 위치를 알 수 있으므로,
    원문 묶음의 영숫자 조각이 모두 남았을 때만 그 조각들이 차지한 압축 결과 구간을 원문 표기로 바꾼다.
    조각이 하나라도 지워졌으면 되돌리지 않는다. 위치로 바꾸므로 다른 곳의 같은 숫자열은 건드리지 않는다.
    반환: (되돌린 문맥, 되돌린 원문 표기 목록, 되돌리지 못한 이유 또는 None)
    """
    try:
        pairs = _parse_word_labels(labeled)
    except ValueError:
        return compressed, [], "unreadable_word_labels"
    words = [word for word, _ in pairs]
    source_spans = _align_words(source, words)
    if source_spans is None:
        return compressed, [], "source_alignment_failed"
    kept = [i for i, (_, keep) in enumerate(pairs) if keep]
    output_spans = _align_words(compressed, [words[i] for i in kept])
    if output_spans is None:
        return compressed, [], "output_alignment_failed"
    output_of = dict(zip(kept, output_spans))

    replacements: list[tuple[int, int, str]] = []
    cursor = 0
    for match in _PUNCTUATED_TOKEN.finditer(source):
        start, end = match.span()
        while cursor < len(words) and source_spans[cursor][1] <= start:
            cursor += 1
        inside = []
        index = cursor
        while index < len(words) and source_spans[index][0] < end:
            inside.append(index)
            index += 1
        # 묶음 경계를 걸친 단어가 있으면 (비 ASCII 글자와 붙은 경우 등) 건드리지 않는다
        if not inside or source_spans[inside[0]][0] < start or source_spans[inside[-1]][1] > end:
            continue
        if not all(pairs[i][1] for i in inside if any(ch.isalnum() for ch in words[i])):
            continue
        pieces = [output_of[i] for i in inside if pairs[i][1]]
        first, last = pieces[0][0], pieces[-1][1]
        if compressed[first:last] != match.group(0):
            replacements.append((first, last, match.group(0)))
    for first, last, value in reversed(replacements):
        compressed = compressed[:first] + value + compressed[last:]
    return compressed, [value for _, _, value in replacements], None


def _missing_identifiers(identifiers: list[str], text: str) -> list[str]:
    missing = []
    for value in identifiers:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])"
        if not re.search(pattern, text):
            missing.append(value)
    return missing


class LLMLingua2Compressor(Compressor):
    """LLMLingua-2 토큰 분류기로 context만 압축한다."""

    targets = ("context",)

    def __init__(
        self,
        *,
        retain_ratio: float = 0.5,
        model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        model_revision: str = "5f0c827",
        device: str = "cpu",
        force_tokens: tuple[str, ...] = DEFAULT_FORCE_TOKENS,
        force_reserve_digit: bool = True,
        fallback_on_error: bool = True,
        rejoin_punctuated: bool = False,
        name: str | None = None,
        engine_factory: Callable[[], Any] | None = None,
    ):
        if not 0 < retain_ratio <= 1:
            raise ValueError("retain_ratio는 0보다 크고 1 이하여야 합니다")
        if not model_name.strip():
            raise ValueError("model_name은 빈 문자열일 수 없습니다")
        if not model_revision.strip():
            raise ValueError("model_revision은 빈 문자열일 수 없습니다")
        if not device.strip():
            raise ValueError("device는 빈 문자열일 수 없습니다")
        if len(force_tokens) > 100:
            raise ValueError("force_tokens는 LLMLingua-2 한도인 100개 이하여야 합니다")

        self.retain_ratio = float(retain_ratio)
        self.model_name = model_name
        self.model_revision = model_revision
        self.device = device
        self.force_tokens = tuple(force_tokens)
        self.force_reserve_digit = force_reserve_digit
        self.fallback_on_error = fallback_on_error
        self.rejoin_punctuated = rejoin_punctuated
        self.name = name or (
            f"llmlingua2_r{round(self.retain_ratio * 100):02d}" + ("_punct" if rejoin_punctuated else "")
        )
        self._engine_factory = engine_factory
        self._engine = None

    @property
    def safety_policy_version(self) -> str:
        # 되돌리기를 끈 압축기는 기존 run 과 같은 값을 남긴다
        return f"{SAFETY_POLICY_VERSION}+{REJOIN_POLICY}" if self.rejoin_punctuated else SAFETY_POLICY_VERSION

    def config(self) -> dict:
        config = {
            "method": "llmlingua2",
            "retain_ratio": self.retain_ratio,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "device": self.device,
            "force_tokens": list(self.force_tokens),
            "force_reserve_digit": self.force_reserve_digit,
            "fallback_on_error": self.fallback_on_error,
            "safety_policy_version": self.safety_policy_version,
        }
        if self.rejoin_punctuated:
            config["rejoin_punctuated"] = True
        return config

    def _get_engine(self):
        if self._engine is None:
            self._engine = (
                self._engine_factory()
                if self._engine_factory is not None
                else _load_engine(self.model_name, self.model_revision, self.device)
            )
        return self._engine

    def _base_info(self) -> dict:
        return {
            "method": "llmlingua2",
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "device": self.device,
            "retain_ratio": self.retain_ratio,
            "force_tokens": list(self.force_tokens),
            "force_reserve_digit": self.force_reserve_digit,
            "safety_policy_version": self.safety_policy_version,
        }

    def _record(
        self,
        *,
        status: str,
        source: str,
        output: str,
        elapsed: float,
        origin_tokens: int | None = None,
        compressed_tokens: int | None = None,
        used_original: bool = False,
        **extra,
    ) -> None:
        removed = (
            origin_tokens - compressed_tokens
            if origin_tokens is not None and compressed_tokens is not None
            else None
        )
        reduction = (
            round(100 * removed / origin_tokens, 4)
            if removed is not None and origin_tokens
            else None
        )
        trace = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "stage": self.name,
            "status": status,
            "input": {
                "characters": len(source),
                "tokens_internal": origin_tokens,
            },
            "output": {
                "characters": len(output),
                "tokens_internal": compressed_tokens,
            },
            "removed_tokens_internal": removed,
            "reduction_pct_internal": reduction,
            "duration_sec": round(elapsed, 4),
            "used_original": used_original,
        }
        self.add_info(**self._base_info(), status=status, trace=trace, **extra)

    def _fallback(
        self,
        status: str,
        source: str,
        elapsed: float,
        *,
        origin_tokens: int | None = None,
        compressed_tokens: int | None = None,
        **extra,
    ) -> str:
        if compressed_tokens is not None:
            extra["attempted_compressed_tokens_internal"] = compressed_tokens
        self._record(
            status=status,
            source=source,
            output=source,
            elapsed=elapsed,
            origin_tokens=origin_tokens,
            # 실제 downstream 입력은 압축 시도 결과가 아니라 원문이다.
            compressed_tokens=origin_tokens,
            used_original=True,
            **extra,
        )
        return source

    def compress_context(self, question: str, context: str) -> str:
        if not context.strip():
            self._record(
                status="unchanged_empty_input",
                source=context,
                output=context,
                elapsed=0.0,
                origin_tokens=0,
                compressed_tokens=0,
                used_original=True,
            )
            return context

        started = time.perf_counter()
        masked_context, protected_units, code_blocks, document_headers = _mask_protected_units(context)
        protected_markers = [marker for marker, _ in protected_units]
        code_markers = [marker for marker, _ in code_blocks]
        header_markers = [marker for marker, _ in document_headers]
        protected_code_characters = sum(len(block) for _, block in code_blocks)
        force_slots = max(0, 100 - len(self.force_tokens))
        required_question_identifiers = _question_identifiers(question, context)
        required_force_tokens = list(dict.fromkeys((*protected_markers, *required_question_identifiers)))
        if len(required_force_tokens) > force_slots:
            return self._fallback(
                "fallback_too_many_protected_units",
                context,
                time.perf_counter() - started,
                required_question_identifiers=required_question_identifiers,
                protected_code_blocks=len(code_blocks),
                protected_code_characters=protected_code_characters,
                protected_document_headers=len(document_headers),
                force_token_slots=force_slots,
            )
        context_identifiers = _protected_identifiers(context, limit=100)
        protected_identifiers = _unsplittable_identifiers(
            masked_context,
            list(dict.fromkeys((*required_question_identifiers, *context_identifiers))),
            already=[*self.force_tokens, *protected_markers],
            slots=max(0, force_slots - len(protected_markers)),
        )
        effective_force_tokens = _longest_first(dict.fromkeys(
            (*self.force_tokens, *protected_markers, *protected_identifiers)
        ))
        try:
            result = self._get_engine().compress_prompt(
                context=[masked_context],
                rate=self.retain_ratio,
                use_context_level_filter=False,
                use_token_level_filter=True,
                force_tokens=effective_force_tokens,
                force_reserve_digit=self.force_reserve_digit,
                **({"return_word_label": True, "word_sep": _LABEL_WORD_SEP} if self.rejoin_punctuated else {}),
            )
            elapsed = time.perf_counter() - started
            if not isinstance(result, dict) or "compressed_prompt" not in result:
                raise ValueError("LLMLingua-2 결과에 compressed_prompt가 없습니다")

            compressed_masked = result["compressed_prompt"]
            if not isinstance(compressed_masked, str):
                raise TypeError("LLMLingua-2 compressed_prompt가 문자열이 아닙니다")

            origin_tokens = int(result["origin_tokens"]) if result.get("origin_tokens") is not None else None
            compressed_tokens = (
                int(result["compressed_tokens"])
                if result.get("compressed_tokens") is not None
                else None
            )

            invalid_code_markers = [
                marker for marker in code_markers if compressed_masked.count(marker) != 1
            ]
            if invalid_code_markers:
                return self._fallback(
                    "fallback_missing_code_block_marker",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    missing_code_block_markers=invalid_code_markers,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )
            invalid_header_markers = [
                marker for marker in header_markers if compressed_masked.count(marker) != 1
            ]
            if invalid_header_markers:
                return self._fallback(
                    "fallback_missing_document_header_marker",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    missing_document_header_markers=invalid_header_markers,
                    protected_document_headers=len(document_headers),
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )
            marker_positions = [compressed_masked.index(marker) for marker in protected_markers]
            if marker_positions != sorted(marker_positions):
                return self._fallback(
                    "fallback_reordered_protected_marker",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_document_headers=len(document_headers),
                    protected_identifiers=protected_identifiers,
                )
            rejoined: list[str] = []
            rejoin_skipped: str | None = None
            if self.rejoin_punctuated:
                # 코드 블록·문서 경계 줄은 마커 상태라 prose 만 되돌린다
                labeled = result.get("fn_labeled_original_prompt")
                if isinstance(labeled, str):
                    compressed_masked, rejoined, rejoin_skipped = _rejoin_punctuated(
                        compressed_masked, masked_context, labeled
                    )
                else:
                    rejoin_skipped = "missing_word_labels"
            compressed = _restore_protected_units(compressed_masked, protected_units)

            if not compressed.strip():
                return self._fallback(
                    "fallback_empty_output",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )
            if (
                origin_tokens is not None
                and compressed_tokens is not None
                and compressed_tokens > origin_tokens
            ):
                return self._fallback(
                    "fallback_larger_output",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )

            source_fences = _fence_counts(context)
            output_fences = _fence_counts(compressed)
            if any(source_fences) and (
                output_fences != source_fences or any(n % 2 for n in output_fences)
            ):
                return self._fallback(
                    "fallback_broken_fence",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    source_fences=list(source_fences),
                    output_fences=list(output_fences),
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )

            marker = "## Document:"
            source_markers = context.count(marker)
            output_markers = compressed.count(marker)
            if source_markers and output_markers < source_markers:
                return self._fallback(
                    "fallback_missing_document_boundary",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    source_document_markers=source_markers,
                    output_document_markers=output_markers,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )

            missing_question_identifiers = _missing_identifiers(
                required_question_identifiers,
                compressed,
            )
            if missing_question_identifiers:
                return self._fallback(
                    "fallback_missing_question_identifier",
                    context,
                    elapsed,
                    origin_tokens=origin_tokens,
                    compressed_tokens=compressed_tokens,
                    required_question_identifiers=required_question_identifiers,
                    missing_question_identifiers=missing_question_identifiers,
                    protected_code_blocks=len(code_blocks),
                    protected_code_characters=protected_code_characters,
                    protected_identifiers=protected_identifiers,
                )

            self._record(
                status="compressed",
                source=context,
                output=compressed,
                elapsed=elapsed,
                origin_tokens=origin_tokens,
                compressed_tokens=compressed_tokens,
                library_ratio=result.get("ratio"),
                library_rate=result.get("rate"),
                library_input_masked=bool(protected_units),
                protected_code_blocks=len(code_blocks),
                protected_code_characters=protected_code_characters,
                protected_document_headers=len(document_headers),
                required_question_identifiers=required_question_identifiers,
                protected_identifiers=protected_identifiers,
                **(
                    {"rejoined_punctuated": rejoined, "rejoin_skipped": rejoin_skipped}
                    if self.rejoin_punctuated
                    else {}
                ),
            )
            return compressed
        except Exception as exc:
            elapsed = time.perf_counter() - started
            if not self.fallback_on_error:
                raise
            return self._fallback(
                "fallback_error",
                context,
                elapsed,
                error_type=exc.__class__.__name__,
                error=_short_error(exc),
                protected_identifiers=protected_identifiers,
            )
