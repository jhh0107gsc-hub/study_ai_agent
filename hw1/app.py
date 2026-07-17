from flask import Flask, render_template
from dotenv import load_dotenv
from anthropic import Anthropic

PROMPT_PIECES = {
    "role": {
        "title": "역할",
        "type": "radio",
        "options": [
            {"label": "일반 도우미", "value": "General assistant"},
            {"label": "친절한 교사","value": "Helpful teacher"},
            {"label": "소프트웨어 개발자","value": "Software developer"},
            {"label": "전문 연구원","value": "Professional researcher"},
            {"label": "창의적인 작가","value": "Creative writer"},
        ]
    },
    "tone": {
        "title": "어조",
        "type": "radio",
        "options": [
            {"label": "친근한", "value": "Friendly"},
            {"label": "격식 있는", "value": "Formal"},
            {"label": "유머러스한", "value": "Humorous"},
            {"label": "자신감 있는", "value": "Confident"},
            {"label": "전문적인", "value": "Professional"}
        ]
    },

    "style": {
        "title": "답변 방식",
        "type": "checkbox",
        "options": [
            {"label": "자세하게", "value": "Detailed"},
            {"label": "간결하게", "value": "Concise"},
            {"label": "단계별 설명", "value": "Step-by-step"},
            {"label": "예시 포함", "value": "With examples"},
            {"label": "글머리표 사용", "value": "Bullet points"}
        ]
    },

    "priority": {
        "title": "우선순위",
        "type": "radio",
        "options": [
            {"label": "정확성", "value": "Accuracy"},
            {"label": "효율성", "value": "Efficiency"},
            {"label": "안전성", "value": "Safety"},
            {"label": "창의성", "value": "Creativity"},
            {"label": "유용성", "value": "Helpfulness"}
        ]
    },

    "rules": {
        "title": "규칙",
        "type": "checkbox",
        "options": [
            {"label": "추측하지 않기", "value": "Never speculate"},
            {"label": "모르면 모른다고 말하기", "value": "Admit uncertainty"},
            {"label": "근거 제시하기", "value": "Cite evidence"},
            {"label": "필요하면 추가 질문하기", "value": "Ask clarifying questions"},
            {"label": "간결하게 답변하기", "value": "Be concise"}
        ]
    }
}

load_dotenv()

app = Flask(__name__)
client = Anthropic()
MODEL = "claude-sonnet-4-6"

@app.route("/")
def index():
    return render_template("index.html", prompt_pieces=PROMPT_PIECES)

if __name__ == "__main__":
    app.run(debug=True, port=5000)