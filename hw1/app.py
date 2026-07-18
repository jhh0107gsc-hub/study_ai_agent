from flask import Flask, render_template, request
from dotenv import load_dotenv
from anthropic import Anthropic

# 프롬프트 조각
PROMPT_PIECES = {
    "role": {
        "title": "역할",
        "type": "radio",
        "options": [
            {
                "label": "일반 도우미",
                "value": "general_assistant",
                "prompt": "도움이 되는 범용 도우미 역할을 수행하세요."
            },
            {
                "label": "친절한 교사",
                "value": "helpful_teacher",
                "prompt": "인내심 있고 격려를 잘하며 풍부한 지식을 갖춘 교사 역할을 수행하세요."
            },
            {
                "label": "소프트웨어 개발자",
                "value": "software_developer",
                "prompt": "깔끔하고 유지보수하기 쉬운 코드를 중요하게 생각하는 숙련된 소프트웨어 개발자 역할을 수행하세요."
            },
            {
                "label": "전문 연구원",
                "value": "professional_researcher",
                "prompt": "전문 연구원 역할을 수행하세요. 답변은 근거와 논리적 추론을 바탕으로 작성하세요."
            },
            {
                "label": "창의적인 작가",
                "value": "creative_writer",
                "prompt": "풍부한 상상력과 흥미로운 이야기 구성 능력을 갖춘 창의적인 작가 역할을 수행하세요."
            }
        ]
    },

    "tone": {
        "title": "어조",
        "type": "radio",
        "options": [
            {
                "label": "친근한",
                "value": "friendly",
                "prompt": "따뜻하고 친근하며 편안하게 다가가는 어조를 사용하세요."
            },
            {
                "label": "격식 있는",
                "value": "formal",
                "prompt": "격식 있고 전문적인 어조를 사용하세요."
            },
            {
                "label": "유머러스한",
                "value": "humorous",
                "prompt": "답변의 품질을 높이는 데 도움이 되는 경우 적절한 유머를 사용하세요."
            },
            {
                "label": "자신감 있는",
                "value": "confident",
                "prompt": "불확실한 정보를 지나치게 단정하지 않으면서 자신감 있게 답변하세요."
            },
            {
                "label": "전문적인",
                "value": "professional",
                "prompt": "답변 전체에서 전문적인 어조를 유지하세요."
            }
        ]
    },

    "styles": {
        "title": "답변 방식",
        "type": "checkbox",
        "options": [
            {
                "label": "자세하게",
                "value": "detailed",
                "prompt": "충분히 자세하고 깊이 있는 설명을 제공하세요."
            },
            {
                "label": "간결하게",
                "value": "concise",
                "prompt": "답변을 간결하고 핵심적으로 작성하세요."
            },
            {
                "label": "단계별 설명",
                "value": "step_by_step",
                "prompt": "과정을 단계별로 나누어 설명하세요."
            },
            {
                "label": "예시 포함",
                "value": "with_examples",
                "prompt": "적절한 경우 실용적인 예시를 포함하세요."
            },
            {
                "label": "글머리표 사용",
                "value": "bullet_points",
                "prompt": "가독성을 높이기 위해 글머리표나 번호 매기기 목록을 사용하세요."
            }
        ]
    },

    "priority": {
        "title": "우선순위",
        "type": "radio",
        "options": [
            {
                "label": "정확성",
                "value": "accuracy",
                "prompt": "무엇보다 사실의 정확성을 우선하세요."
            },
            {
                "label": "효율성",
                "value": "efficiency",
                "prompt": "효율적이고 실용적인 해결 방법을 우선하세요."
            },
            {
                "label": "안전성",
                "value": "safety",
                "prompt": "안전하고 책임감 있으며 윤리적인 답변을 우선하세요."
            },
            {
                "label": "창의성",
                "value": "creativity",
                "prompt": "독창성과 창의적인 사고를 우선하세요."
            },
            {
                "label": "유용성",
                "value": "helpfulness",
                "prompt": "가능한 한 유용하고 실제로 활용할 수 있는 답변을 제공하는 것을 우선하세요."
            }
        ]
    },

    "rules": {
        "title": "규칙",
        "type": "checkbox",
        "options": [
            {
                "label": "추측하지 않기",
                "value": "no_speculation",
                "prompt": "정보를 추측하거나 지어내지 마세요."
            },
            {
                "label": "모르면 모른다고 말하기",
                "value": "admit_uncertainty",
                "prompt": "확신이 없거나 충분한 정보가 없는 경우 그 사실을 명확하게 밝히세요."
            },
            {
                "label": "근거 제시하기",
                "value": "cite_evidence",
                "prompt": "가능한 경우 중요한 주장에는 논리적 근거나 증거를 제시하세요."
            },
            {
                "label": "필요하면 추가 질문하기",
                "value": "ask_clarifying_questions",
                "prompt": "사용자의 요청이 모호하거나 정보가 부족한 경우 추가 질문을 하세요."
            },
            {
                "label": "간결하게 답변하기",
                "value": "be_concise",
                "prompt": "불필요하게 장황한 설명은 피하세요."
            }
        ]
    }
}

load_dotenv()

app = Flask(__name__)
client = Anthropic()
MODEL = "claude-haiku-4-5"

@app.route("/")
def index():
    return render_template("index.html", prompt_pieces=PROMPT_PIECES)

@app.route("/generate", methods=["POST"])
def generate():
    """
    사용자의 질문과 함께 선택된 프롬프트를 시스템 프롬프트로 하여 LLM을 호출, 응답을 반환하는 함수
    """
    # Content-Type: application/json 헤더를 확인하여 JSON 형식의 문자열을 파이썬의 객체로 변환
    request_data = request.get_json()

    # 요청 데이터에서 질문을 빼내어 저장
    question = request_data.pop("question")

    role = request_data.get("role") # String
    tone = request_data.get("tone") # String or None
    styles = request_data.get("styles") # list
    priority = request_data.get("priority") # String or None
    rules = request_data.get("rules") # list

    print(request_data)

    # 시스템 프롬프트를 담을 리스트
    prompt_sentences = []

    # 선택한 프롬프트 조각들을 순회
    for category_name, selected_value in request_data.items():

        # 각 카테고리의 값은 단일 값을 가지는 radio 타입의 경우 문자열, 다중 값을 가지는 checkbox 타입의 경우 문자열 리스트를 가진다.
        # 따라서 비어있는 값은 명시적으로 None 또는 []을 전달받아 처리한다.

        # 비어있는 카테고리는 pass
        if not selected_value:
            continue

        # 전체 프롬프트 조각에서 카테고리를 가져오기
        category = PROMPT_PIECES.get(category_name)

        # radio 타입의 경우 하나의 프롬프트를 찾아 추가 -> == 연산자
        if category["type"] == "radio":
            for option in category["options"]:
                if option["value"] == selected_value:
                    prompt_sentences.append(option["prompt"])

        # checkbox 타입의 경우 여러 프롬프트를 찾아 추가 -> in 연산자
        elif category["type"] == "checkbox":
            for option in category["options"]:
                if option["value"] in selected_value:
                    prompt_sentences.append(option["prompt"])

    system_prompt = "\n".join(prompt_sentences)

    print(system_prompt)

    # LLM 호출
    message = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"{question}"
            }
        ]
    )

    print(message.content[0].text)

    # JSON 형식으로 응답을 담아 반환
    return {
        "response": message.content[0].text
    }

if __name__ == "__main__":
    app.run(debug=True, port=5000)