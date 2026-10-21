import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

if getattr(settings, 'USE_UNFOLD', False):
    from unfold.widgets import INPUT_CLASSES, SELECT_CLASSES, TEXTAREA_CLASSES
else:
    # The stock admin styles these elements globally; Unfold puts the styling
    # in widget classes, so the raw controls need the same classes here.
    INPUT_CLASSES = ()
    SELECT_CLASSES = ()
    TEXTAREA_CLASSES = ()

_TICKED = {"true", "1", "yes", "on", "ja"}


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TICKED


def _question_rows(questions):
    """Return (key, label, kind) triples for the event's registration fields."""
    rows = []
    for question in questions:
        if question.type == "select":
            kind = "select"
        elif question.type == "checkbox":
            kind = "checkbox"
        else:
            kind = "text"
        rows.append((str(question), str(question), kind))
    return rows


class EventAnswersWidget(forms.Widget):
    """Edit one participant's answers as fields instead of raw JSON.

    The widget renders one control per ``EventRegistrationForm`` row of the
    event: a text input, a choice select, or a yes/no select for checkbox
    questions. Answers whose question no longer exists stay editable as plain
    values and are marked as orphans so an editor knows why the field looks
    unfamiliar.
    """

    template_name = "events/event_answers_widget.html"

    def __init__(self, questions=None, attrs=None, compact=False):
        self.questions = list(questions or ())
        self.compact = compact
        super().__init__(attrs=attrs)

    def _answers(self, value):
        if isinstance(value, list):
            return {}
        if isinstance(value, str) and value.strip():
            try:
                value = json.loads(value)
            except ValueError:
                return {}
        if not isinstance(value, dict):
            return {}
        return value

    def _answer_rows(self, value):
        answers = self._answers(value)
        rows = []
        known = set()
        for key, label, kind in _question_rows(self.questions):
            known.add(key)
            current = answers.get(key, "")
            if isinstance(current, (dict, list)):
                kind = "json"
                current = json.dumps(current, ensure_ascii=False, indent=2)
            elif kind == "checkbox":
                current = _as_bool(current)
            elif current is None:
                current = ""
            elif not isinstance(current, str):
                current = str(current)
            rows.append(
                {
                    "key": key,
                    "label": label,
                    "kind": kind,
                    "value": current,
                    "choices": self._choices(key, current),
                    "is_orphan": False,
                }
            )

        for key, current in answers.items():
            if key in known:
                continue
            if isinstance(current, bool):
                rows.append(
                    {
                        "key": key,
                        "label": key,
                        "kind": "checkbox",
                        "value": current,
                        "choices": [],
                        "is_orphan": True,
                    }
                )
            elif isinstance(current, (dict, list)):
                rows.append(
                    {
                        "key": key,
                        "label": key,
                        "kind": "json",
                        "value": json.dumps(current, ensure_ascii=False, indent=2),
                        "choices": [],
                        "is_orphan": True,
                    }
                )
            else:
                rows.append(
                    {
                        "key": key,
                        "label": key,
                        "kind": "text",
                        "value": "" if current is None else str(current),
                        "choices": [],
                        "is_orphan": True,
                    }
                )
        return rows

    def _choices(self, key, current):
        for question in self.questions:
            if str(question) != key or question.type != "select":
                continue
            choices = question.get_choices()
            # An answer saved before the option list changed must stay visible,
            # otherwise saving the form would silently replace it.
            if isinstance(current, str) and current and current not in choices:
                choices.insert(0, current)
            return choices
        return []

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        base_id = attrs.get("id") or f"id_{name}"
        rows = self._answer_rows(value)
        for index, row in enumerate(rows):
            row["input_id"] = f"{base_id}_answer_{index}"
        context = {
            "name": name,
            "rows": rows,
            "compact": self.compact,
            "input_class": " ".join(INPUT_CLASSES),
            "select_class": " ".join(SELECT_CLASSES),
            "textarea_class": " ".join(TEXTAREA_CLASSES),
        }
        return render_to_string(self.template_name, context)

    def value_from_datadict(self, data, files, name):
        # Fall back to the old single textarea for posts that do not carry the
        # per-question inputs (for example an external integration or a test
        # posting JSON straight at the admin).
        if f"{name}__key__0" not in data:
            return data.get(name)

        answers = {}
        index = 0
        while True:
            key = data.get(f"{name}__key__{index}")
            if key is None:
                break
            raw = data.get(f"{name}__value__{index}")
            if raw is not None:
                kind = data.get(f"{name}__kind__{index}", "text")
                if kind == "checkbox":
                    answers[str(key)] = _as_bool(raw)
                elif kind == "json":
                    try:
                        answers[str(key)] = json.loads(raw)
                    except (TypeError, ValueError) as exc:
                        raise ValidationError(
                            _('Svaret för "%(field)s" är inte giltig JSON.') % {"field": key}
                        ) from exc
                else:
                    answers[str(key)] = raw
            index += 1
        return answers

    @property
    def media(self):
        return forms.Media(css={"all": ("events/css/admin_event_answers.css",)})
