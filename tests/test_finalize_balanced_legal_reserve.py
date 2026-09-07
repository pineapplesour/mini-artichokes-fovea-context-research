from tools.finalize_balanced_legal_reserve import refined_label


def row(label: str, holding: str) -> dict[str, str]:
    return {"caseId": "x", "label": label, "holding": holding}


def test_refined_label_recovers_partial_grants_and_keeps_full_dismissal():
    assert refined_label(row("기각", "1. 배당표 중 원고 배당액을 변경한다.\n2. 원고의 나머지 청구를 기각한다.")) == "인용됨"
    assert refined_label(row("기각", "1. 피고는 원고로 하여금 장부를 열람하도록 하여야 한다.\n2. 나머지 청구를 기각한다.")) == "인용됨"
    assert refined_label(row("기각", "1. 원고들과 나머지 선정자들의 청구를 모두 기각한다.")) == "기각"


def test_refined_label_excludes_appellate_disposition():
    assert refined_label(row("기각", "1. 제1심판결을 다음과 같이 변경한다.\n2. 원고의 나머지 청구를 기각한다.")) is None
