// 페이지 로드 시 전역에서 세션 생성, 현재 페이지에서 통용된다. 
const sessionId = crypto.randomUUID();

let currentPersona = null;
let isStreaming = false;

// DOM 요소 취득
const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");

const modelSelect = document.getElementById("model-select");

const tempSlider = document.getElementById("temperature");
const tempValue = document.getElementById("temp-value");

const tokensSlider = document.getElementById("max-tokens");
const tokensValue = document.getElementById("tokens-value");

const tokenInfo = document.getElementById("token-info");

userInput.disabled = true;
sendBtn.disabled = true;
resetBtn.disabled = true;

// 슬라이더 표시
tempSlider.oninput = () => tempValue.textContent = tempSlider.value;
tokensSlider.oninput = () => tokensValue.textContent = tokensSlider.value;

// 페르소나 선택
function selectPersona(personaId) {
    // 클릭한 페르소나를 현재 페르소나로 설정
    currentPersona = personaId;

    document.querySelectorAll(".persona-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.persona === personaId);
    });

    // 페르소나 선택 후 입력, 전송, 초기화 가능
    userInput.disabled = false;
    sendBtn.disabled = false;
    resetBtn.disabled = false;

    // resetChat()은 비동기 함수로 내부의 await fetch()을 만난 뒤, Promise가 완료될 때까지 중지된다.
    // selectPersona()로 제어권이 넘어와 아래의 동기 코드를 실행한다.
    // 요청에 대한 응답이 돌아오면 resetChat()을 재개한다.
    // 따라서 아래 코드는 resetChat() 종료 전에 이미 실행된 상태이다.
    resetChat();

    chatBox.innerHTML = `
        <div class="system-message">
            <strong>${document.querySelector(`[data-persona="${personaId}"] strong`).textContent}</strong>
            페르소나로 대화를 시작합니다.
        </div>
    `;

    userInput.focus();
}

// 메세지 추가
function appendMessage(role, text) {

    const div = document.createElement("div");
    div.className = `message ${role}`;

    const roleSpan = document.createElement("span");
    roleSpan.className = "role";
    roleSpan.textContent = role === "user" ? "나" : "AI";

    const textSpan = document.createElement("span");
    textSpan.className = "text";
    textSpan.textContent = text;

    div.append(roleSpan, textSpan);

    chatBox.appendChild(div);

    chatBox.scrollTop = chatBox.scrollHeight;

    return div;
}

// 메세지 전송
async function sendMessage() {

    const message = userInput.value.trim();

    // 메세지가 전송되면 안되는 경우
    // 1. 메세지가 비어있거나
    // 2. 선택된 현재 페르소나가 없거나
    // 3. 현재 스트리밍 응답을 받고 있거나
    if (!message || !currentPersona || isStreaming) return;

    isStreaming = true;

    // 입력한 메세지를 채팅 창에 추가
    appendMessage("user", message);

    // 메세지 전송 중에는 또 다른 메세지 전송 불가
    userInput.value = "";
    userInput.disabled = true;
    sendBtn.disabled = true;

    // LLM 응답을 채울 빈 메세지 창을 만들고 그 창을 반환받음
    const assistantDiv = appendMessage("assistant", "");

    try {
        // 응답이 올 때까지 sendMessage() 일시 중단, 대기
        const response = await fetch("/chat", {
            method: "POST",
            // JSON 형식으로 body에 담아 보내겠다고 헤더를 설정
            headers: {
                "Content-Type": "application/json"
            },

            // JS 객체 -> JSON 형식으로 변환
            // 세션, 페르소나, 모델, 메세지, temperature, max_tokens을 담아 보낸다.
            body: JSON.stringify({
                session_id: sessionId,
                persona: currentPersona,
                model: modelSelect.value,

                message: message,
                temperature: parseFloat(tempSlider.value),
                max_tokens: parseInt(tokensSlider.value),
            })
        });
        
        // 일반적으로 응답에 대해 response.json()으로 하나의 전체 응답을 읽겠지만,
        // 현재 코드에서는 SSE 방식으로 스트리밍하기 때문에 response.body의 Reader 객체를 생성하여
        // response.body의 스트림을 순차적으로 읽을 수 있다.
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = "";

        while (true) {
            // reader.read()는 데이터가 직접 들어있는 함수가 아닌 데이터를 가져오는 함수
            // 프라미스를 반환하여 작업이 완료되면 value에는 바이트 데이터로 표현된 토큰이 들어 있다.
            // done은 스트림이 종료되어 더 이상 읽을 데이터가 없음을 의미한다.

            // {
            //  value: Uint8Array("data: {\"text\":\"생성한 토큰\"}\n\n"),
            //  done: false
            // }

            const { done, value } = await reader.read();

            if (done) break;

            // 문자열로 변환
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");

            // 잘은 모르겠지만 마지막 줄은 덜 온 것일 수도 있으니 다음 데이터와 합치기 전까지 보관
            buffer = lines.pop();

            for (const line of lines) {
                // SSE의 형식인 data: {"text": "토큰"} 임을 확인
                if (!line.startsWith("data: ")) continue;

                // [:6]인 "data:"를 제거하여 {"text": "토큰"} 만 남기고, JS 객체로 변환
                const data = JSON.parse(line.slice(6));
                
                if (data.text) {
                    // 토큰을 붙여가며 화면에 표시
                    assistantDiv.querySelector(".text").textContent += data.text;

                    chatBox.scrollTop = chatBox.scrollHeight;
                }
                
                // 응답이 전부 끝난 뒤, 명시적으로 "finished": True가 전달되면
                if (data.finished) {
                    // 입출력 토큰 정보와 소요 시간을 화면에 표시
                    tokenInfo.textContent =
                        `입력 ${data.input_tokens}토큰 / 출력 ${data.output_tokens}토큰 / 소요 시간 : ${data.elapsed}초`
                }
            }
        }

    } catch {
        assistantDiv.querySelector(".text").textContent =
            "[오류] 응답을 받지 못했습니다.";
    }

    isStreaming = false;

    userInput.disabled = false;
    sendBtn.disabled = false;

    userInput.focus();
}

// 초기화
async function resetChat() {
    // 선택된 페르소나가 없다면 종료
    if (!currentPersona) return;

    await fetch("/reset", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },

        // 세션, 페르소나, 모델을 담아 보낸다.
        body: JSON.stringify({
            persona: currentPersona,
            model: modelSelect.value,
            session_id: sessionId
        })
    });

    tokenInfo.textContent = "";
}

// 이벤트 등록
document.querySelectorAll(".persona-btn").forEach(btn => {
    btn.addEventListener("click", () => selectPersona(btn.dataset.persona));
});

sendBtn.addEventListener("click", sendMessage);
resetBtn.addEventListener("click", resetChat);

userInput.addEventListener("keydown", e => {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});