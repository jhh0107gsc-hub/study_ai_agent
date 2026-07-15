import json
import time
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv, find_dotenv
from anthropic import (
    Anthropic,
    APIError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
    BadRequestError,
    NotFoundError,
)

load_dotenv()

PERSONAS = {
    "teacher": {
        "name": "선생님",
        "description": "쉽게 설명",
        "system": (
            # Role: AI가 맡을 역할
            "당신은 프로그래밍을 처음 배우는 학생을 가르치는 친절한 선생님입니다. "
            # Tone: 답변 말투와 분위기
            "항상 존댓말을 사용하고, 격려하는 톤으로 말합니다. "
            # Scope: 주로 답할 주제 범위
            "프로그래밍 관련 질문에 대해 비유와 예시를 들어 쉽게 설명합니다. "
            # Rules: 답변할 때 지켜야 할 규칙
            "코드 예시를 보여줄 때는 반드시 한 줄씩 설명을 덧붙입니다. "
            "프로그래밍과 무관한 질문에는 '좋은 질문이지만, 프로그래밍 관련 내용을 함께 이야기해봐요!'라고 안내합니다."
        ),
    },
    "cycle_coach": {
        "name": "자전거 코치",
        "description": "이해하기 쉽게 수치와 함께 설명",
        "system": (
            # Role: AI가 맡을 역할
            "당신은 오랜 기간동안 사이클 선수들의 훈련을 책임진 전문가 입니다. "
            # Tone: 답변 말투와 분위기
            "기본적으로 냉철하지만, 할 수 있다는 마음으로 상대방을 격려하는 따뜻한 말을 건넵니다. "
            # Scope: 주로 답할 주제 범위
            "자전거 관련 질문에 대해 정량적인 수치 비교를 통해 명확하게 설명합니다. "
            # Rules: 답변할 때 지켜야 할 규칙
            "훈련에 대해 설명할 때에는 한 가지 뿐만 아니라 여러 안을 함께 제시합니다. "
            "자전거 무관한 질문에는 잘은 모르겠으나, 일반적인 상식 수준에서 대답합니다. "
        ),
    },
}

MODELS = {
    "haiku": {
        "id": "claude-haiku-4-5",
        "name": "Haiku 4.5",
        "description": "빠르고 저렴 — 간단한 작업에 적합",
    },
    "sonnet": {
        "id": "claude-sonnet-4-6",
        "name": "Sonnet 4.6",
        "description": "속도와 성능의 균형 — 범용",
    },
    "opus": {
        "id": "claude-opus-4-8",
        "name": "Opus 4.8",
        "description": "최고 성능 — 복잡한 추론에 적합",
    },
}

app = Flask(__name__)

client = Anthropic()

# 세션 / 페르소나 / 모델의 조합 별로 대화 히스토리를 저장하는 딕셔너리
conversations: dict[str, list] = {}

# 인덱스 페이지, 페르소나와 모델 종류를 보냄
@app.route("/")
def index():
    return render_template("index.html", personas=PERSONAS, models=MODELS)

@app.route("/chat", methods=["POST"])
def chat():
    """
    선택한 페르소나와 모델, 생성 파라미터를 사용하여
    Claude를 호출하고 SSE로 스트리밍합니다.
    """

    # 클라이언트 요청의 JSON 데이터를 파이썬 딕셔너리로 변환
    data = request.json

    # 딕셔너리에서 세션, 페르소나, 모델 정보 가져오기
    session_id = data.get("session_id", "default")
    persona_id = data["persona"]
    model_key = data["model"]
    
    # 그리고, 메세지와 함께 temperature, max_tokens 파라미터 가져오기
    user_message = data["message"]
    temperature = float(data.get("temperature", 1.0))
    max_tokens = int(data.get("max_tokens", 1024))

    # 현재 세션 / 페르소나 / 모델 조합으로 대화를 구별할 키로 설정
    conv_key = f"{session_id}_{persona_id}_{model_key}"

    # 대화 목록에 키로 하여 추가
    if conv_key not in conversations:
        conversations[conv_key] = []

    # 메세지 담기
    history = conversations[conv_key]
    history.append({
        "role": "user",
        "content": user_message
    })
    
    # 페르소나 정보, LLM 호출에 필요한 모델 이름 가져오기
    persona = PERSONAS[persona_id]
    model_id = MODELS[model_key]["id"]


    def generate():
        """
        스트리밍 방식으로 토큰을 생성합니다.
        """
        start_time = time.perf_counter()

        try:
        # 모델, 시스템 프롬프트, 메세지와 함께 파라미터 temperature, max_tokens을 보낸다.
            with client.messages.stream(
                model=model_id,
                system=persona["system"],
                temperature=temperature,
                max_tokens=max_tokens,
                messages=history,
            ) as stream:
                full_response = ""

                # 생성된 문자열 토큰을 받을 때 마다 SSE 형식으로 데이터를 보내기
                # 클라이언트는 "data: JSON 문자열" 형식으로 응답을 받는다.

                # 아래의 Response에 의해 generate 가 반환하는 제네레이터 객체의 next 메서드를 호출하며 이 코드를 동작시킨다.
                # stream.text_stream 은 동기이기 때문에 Claude가 토큰을 보내오기 전까지 잠시 멈췄다가
                # 토큰이 도착하면 클라이언트로 전송하고 next 메서드가 호출되어 다음 토큰을 기다리는 과정을 반복한다.
                for text in stream.text_stream:
                    full_response += text
                    yield f"data: {json.dumps({'text': text})}\n\n"

                # 만약 응답이 끝났다면, Anthropic SDK에서 응답이 종료됨을 알려 stream.text_stream을 끝낸다.
                # 이후 전체 완성된 응답을 히스토리에 추가한다.
                history.append({
                    "role": "assistant",
                    "content": full_response
                })

                elapsed = get_elapsed_time(start_time)

                # stream.get_final_message()은 Claude의 최종 응답으로, usage는 토큰 정보를 담고 있다.
                usage = stream.get_final_message().usage

                # 제네레이터에서 마지막으로 응답이 종료되었음을 명시적으로 알리며, 토큰 정보와 소요 시간을 함께 보낸다.
                yield f"data: {json.dumps({
                    'finished': True,
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'elapsed': elapsed
                })}\n\n"

        # 잘못된 모델명, 기존 모델명이 더 이상 지원되지 않을 때
        except NotFoundError:
            elapsed = get_elapsed_time(start_time)
            yield error_handler("잘못된 모델명, 다른 모델을 시도해주세요.", elapsed)

        except BadRequestError:
            elapsed = get_elapsed_time(start_time)
            yield error_handler("잘못된 모델명, 다른 모델을 시도해주세요.", elapsed)

        # 잘못된 API 키, 키가 만료되어 더 이상 사용할 수 없을 때
        except AuthenticationError:
            elapsed = get_elapsed_time(start_time)
            yield error_handler("잘못된 API 키입니다.", elapsed)

    # Response는 Flask의 HTTP 응답 객체이다.
    # 인수로 제네레이터 객체를 전달함으로써 제네레이터를 반복하며 yield하는 토큰이 담긴 문자열을 보낸다.
    # 또한 클라이언트에게 이 응답이 SSE 형식임을 알려주는 text/event-stream 헤더를 보낸다.
    return Response(
        generate(),
        content_type="text/event-stream",
    )

@app.route("/reset", methods=["POST"])
def reset():
    """
    현재 페르소나와 모델의 대화를 초기화합니다.
    """
    data = request.json

    session_id = data.get("session_id", "default")
    persona_id = data.get("persona", "")
    model_key = data.get("model", "")

    conv_key = f"{session_id}_{persona_id}_{model_key}"

    conversations.pop(conv_key, None)

    return {"status": "ok"}

def error_handler(error_msg, elapsed):
    return f"data: {json.dumps({
        'finished': True,
        'error': error_msg,
        'elapsed': elapsed
    })}\n\n"

def get_elapsed_time(start_time):
    return round(time.perf_counter() - start_time, 2)


if __name__ == "__main__":
    app.run(debug=True, port=5000)