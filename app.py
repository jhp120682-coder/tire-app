import os
import re
import requests
import gradio as gr

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()


def clean_html(text):
    return re.sub(r"<.*?>", "", text)


def normalize_text(text):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", text).lower()


def extract_size_parts(size):
    numbers = re.sub(r"[^0-9]", "", str(size))

    if len(numbers) == 7:
        return numbers[:3], numbers[3:5], numbers[5:7]

    return None, None, None


def normalize_tire_size(size):
    width, ratio, inch = extract_size_parts(size)

    if width:
        return f"{width} {ratio} {inch}"

    return size


def title_has_exact_size(title, tire_size):
    width, ratio, inch = extract_size_parts(tire_size)

    if not width:
        return False

    title_numbers = re.sub(r"[^0-9]", "", title)

    if f"{width}{ratio}{inch}" in title_numbers:
        return True

    pattern = rf"{width}[^0-9]{{0,3}}{ratio}[^0-9]{{0,3}}R?[^0-9]{{0,3}}{inch}"
    return re.search(pattern, title.upper()) is not None


def is_target_tire(title, tire_size, product_name):
    if not title_has_exact_size(title, tire_size):
        return False

    title_norm = normalize_text(title)

    keywords = [
        normalize_text(word)
        for word in product_name.split()
        if normalize_text(word)
    ]

    if not keywords:
        return False

    return all(keyword in title_norm for keyword in keywords)


def search_naver(query):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("Hugging Face Secrets에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 설정해야 합니다.")

    url = "https://openapi.naver.com/v1/search/shop.json"

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display": 100,
        "start": 1,
        "sort": "asc",
        "exclude": "used:rental:cbshop",
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)

    if response.status_code != 200:
        raise ValueError(f"네이버 API 오류: {response.status_code} / {response.text}")

    return response.json().get("items", [])


def tire_search(tire_size, product_name):
    tire_size = str(tire_size).strip()
    product_name = str(product_name).strip()

    if not tire_size or not product_name:
        return []

    query = f"{normalize_tire_size(tire_size)} {product_name} 타이어"

    items = search_naver(query)

    rows = []

    for item in items:
        title = clean_html(item.get("title", ""))

        if not is_target_tire(title, tire_size, product_name):
            continue

        price = int(item.get("lprice", 0))

        rows.append([
            title,
            item.get("mallName", ""),
            price,
            "확인 필요",
            price,
            item.get("link", ""),
        ])

    rows.sort(key=lambda x: x[2])

    ranked_rows = []

    for i, row in enumerate(rows, start=1):
        ranked_rows.append([i] + row)

    return ranked_rows


with gr.Blocks(title="타이어 최저가 검색기") as demo:
    gr.Markdown("# 🚗 타이어 최저가 검색기")
    gr.Markdown("타이어 사이즈와 제품명을 입력하면 정확히 일치하는 상품만 가격순으로 정리합니다.")

    tire_size = gr.Textbox(
        label="타이어 사이즈",
        placeholder="예: 2255517"
    )

    product_name = gr.Textbox(
        label="제품명",
        placeholder="예: 쿠퍼 이볼루션"
    )

    search_btn = gr.Button("검색")

    result = gr.Dataframe(
        headers=["순위", "상품명", "쇼핑몰", "상품가격", "배송비", "총액", "링크"],
        datatype=["number", "str", "str", "number", "str", "number", "str"],
        label="검색 결과",
        interactive=False,
    )

    search_btn.click(
        fn=tire_search,
        inputs=[tire_size, product_name],
        outputs=result,
    )


if __name__ == "__main__":
    demo.launch(ssr_mode=False)