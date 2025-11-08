from typing import Dict

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    _HF_AVAILABLE = True
except Exception:
    _HF_AVAILABLE = False


_MODEL_ID = 'sshleifer/tiny-gpt2'  # маленькая демо-модель для быстрого старта
_tokenizer = None
_model = None


def _lazy_load():
    global _tokenizer, _model
    if not _HF_AVAILABLE:
        return False
    if _tokenizer is None or _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        _model = AutoModelForCausalLM.from_pretrained(_MODEL_ID)
    return True


def _fallback_template(doc_type: str, params: Dict[str, str]) -> str:
    client = params.get('client', 'Клиент')
    total = params.get('total', '0')
    details = params.get('details', '')
    if doc_type == 'invoice':
        return f"Счет на оплату\nПлательщик: {client}\nСумма: {total}\nНазначение: {details}\n"
    if doc_type == 'act':
        return f"Акт выполненных работ\nЗаказчик: {client}\nСумма: {total}\nДетали: {details}\n"
    return f"Договор\nСтороны: {client} и Исполнитель\nСумма: {total}\nПредмет: {details}\n"


def generate_document_text(doc_type: str, params: Dict[str, str]) -> str:
    prompt = (
        f"Сгенерируй {doc_type} на русском языке. Клиент: {params.get('client','')}. "
        f"Сумма: {params.get('total','')}. Детали: {params.get('details','')}\n"
        "Текст: "
    )
    if _lazy_load():
        try:
            input_ids = _tokenizer.encode(prompt, return_tensors='pt')
            out = _model.generate(input_ids, max_new_tokens=80, do_sample=True, top_k=50, top_p=0.95)
            text = _tokenizer.decode(out[0], skip_special_tokens=True)
            return text
        except Exception:
            pass
    return _fallback_template(doc_type, params)

