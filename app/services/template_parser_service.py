from typing import Dict, Any, List, Optional, Tuple
import re

FLAGS = {
    "DOTALL": re.DOTALL,
    "MULTILINE": re.MULTILINE,
    "IGNORECASE": re.IGNORECASE,
    "UNICODE": re.UNICODE,
}


class TemplateParserService:

    @staticmethod
    def compile_re(pattern: str, flag_names: Optional[List[str]]) -> re.Pattern:
        flags = 0
        for f in (flag_names or []):
            flags |= FLAGS.get(str(f).upper().strip(), 0)
        return re.compile(pattern, flags=flags)

    @staticmethod
    def cleanup_text(text: str, cleanup: Dict[str, Any]) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        for rep in cleanup.get("replace", []) or []:
            pat = rep.get("pattern")
            repl = rep.get("replacement", "")
            if pat:
                text = re.sub(pat, repl, text)

        drop_page_numbers = bool(cleanup.get("drop_page_number_lines", False))
        drop_patterns = cleanup.get("drop_lines_matching", []) or []
        drop_rxs = [re.compile(p) for p in drop_patterns if isinstance(p, str) and p]

        out_lines: List[str] = []
        for line in text.splitlines():
            if drop_page_numbers and re.fullmatch(r"\s*\d+\s*", line):
                continue
            if any(rx.search(line.strip()) for rx in drop_rxs):
                continue
            out_lines.append(line.rstrip())
        text = "\n".join(out_lines)

        if cleanup.get("join_hyphenated_words", False):
            text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

        if cleanup.get("collapse_whitespace", False):
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    @staticmethod
    def split_records(text: str, start_pat: str, start_flags: List[str]) -> List[str]:
        start_rx = TemplateParserService.compile_re(start_pat, start_flags)
        starts = [m.start() for m in start_rx.finditer(text)]
        if not starts:
            return []

        blocks: List[str] = []
        for i, s in enumerate(starts):
            e = starts[i + 1] if i + 1 < len(starts) else len(text)
            blocks.append(text[s:e].strip())
        return blocks

    @staticmethod
    def normalize_ws(s: str) -> str:
        s = re.sub(r"\s*\n\s*", " ", s).strip()
        s = re.sub(r"\s{2,}", " ", s)
        return s

    @staticmethod
    def apply_transform(raw: Optional[str], fd: Dict[str, Any]) -> Any:
        if raw is None:
            return None
        v = raw.strip()

        if fd.get("normalize_whitespace", False):
            v = TemplateParserService.normalize_ws(v)

        t = str(fd.get("type", "str")).lower()
        if t == "int":
            m = re.search(r"-?\d+", v)
            return int(m.group(0)) if m else None
        if t == "float":
            m = re.search(r"-?\d+(?:\.\d+)?", v)
            return float(m.group(0)) if m else None
        if t == "list":
            sep = fd.get("split", ",")
            parts = v.split(sep)
            if fd.get("item_strip", True):
                parts = [p.strip() for p in parts]
            parts = [p for p in parts if p]
            return parts
        return v

    @staticmethod
    def extract_fields_from_record(record_text: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        hits: List[Tuple[int, int, str, Dict[str, Any]]] = []

        for fd in fields:
            key = fd["key"]
            flags = fd.get("flags", [])
            label_patterns: List[str] = []

            if isinstance(fd.get("labels"), list):
                label_patterns = [p for p in fd["labels"] if isinstance(p, str)]

            best_span = None
            for pat in label_patterns:
                rx = TemplateParserService.compile_re(pat, flags)
                m = rx.search(record_text)
                if m:
                    span = (m.start(), m.end())
                    if best_span is None or span[0] < best_span[0]:
                        best_span = span

            if best_span:
                hits.append((best_span[0], best_span[1], key, fd))

        hits.sort(key=lambda x: x[0])
        out: Dict[str, Any] = {fd["key"]: None for fd in fields}

        for i, (s, e, key, fd) in enumerate(hits):
            next_start = hits[i + 1][0] if i + 1 < len(hits) else len(record_text)
            out[key] = TemplateParserService.apply_transform(record_text[e:next_start].strip(), fd)

        return out

    @staticmethod
    def raw_record_single_line(raw: str) -> str:
        raw = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)
        raw = re.sub(r"\s*\n\s*", " ", raw).strip()
        raw = re.sub(r"\s{2,}", " ", raw)
        return raw

    @staticmethod
    def parse_pdf(text: str, template: Dict[str, Any]) -> Any:
        cleanup_cfg = template.get("pdf_text_cleanup", {}) or {}
        if cleanup_cfg:
            text = TemplateParserService.cleanup_text(text, cleanup_cfg)

        rec_cfg = template.get("record", {})
        start_pat = rec_cfg["start"]["pattern"]
        start_flags = rec_cfg["start"].get("flags", [])
        fields = template["fields"]
        output_cfg = template.get("output", {"as_dict": False, "id_field": "id"})
        skip_missing = bool(output_cfg.get("skip_records_missing_required", False))
        max_chars = rec_cfg.get("max_record_chars")

        records = TemplateParserService.split_records(text, start_pat, start_flags)
        required_keys = [fd["key"] for fd in fields if fd.get("required")]
        parsed: List[Dict[str, Any]] = []

        for r in records:
            if isinstance(max_chars, int) and max_chars > 0:
                r = r[:max_chars]

            obj = TemplateParserService.extract_fields_from_record(r, fields)

            if required_keys and skip_missing:
                bad = any(obj.get(k) in (None, "", []) for k in required_keys)
                if bad:
                    continue

            if output_cfg.get("include_raw_record", False):
                obj["raw_record"] = TemplateParserService.raw_record_single_line(r)

            parsed.append(obj)

        if output_cfg.get("as_dict", False):
            id_field = output_cfg.get("id_field", "id")
            return {str(o.get(id_field)): o for o in parsed if o.get(id_field) is not None}

        return parsed

    @staticmethod
    def validate_parsed_records(records: List[Dict[str, Any]], fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_records = len(records)
        field_coverage = {}

        for fd in fields:
            key = fd["key"]
            filled_count = sum(1 for r in records if r.get(key) is not None)
            field_coverage[key] = {
                'filled': filled_count,
                'total': total_records,
                'percentage': round((filled_count / total_records * 100), 2) if total_records > 0 else 0,
                'required': fd.get('required', False)
            }

        required_keys = [fd["key"] for fd in fields if fd.get('required', False)]
        successful_records = 0

        if required_keys:
            for record in records:
                if all(record.get(k) is not None for k in required_keys):
                    successful_records += 1
        else:
            successful_records = total_records

        return {
            'total_records': total_records,
            'successful_records': successful_records,
            'success_rate': round((successful_records / total_records * 100), 2) if total_records > 0 else 0,
            'field_coverage': field_coverage
        }
