// 페이지가 로드될 때 세션을 생성하며 현재 페이지에서 사용한다.
const sessionId = crypto.randomUUID();

let currentPersona = null;
let isStreaming = false;

// DOM 요소 가져오기
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

// 페르소나를 선택하기 전에는 입력할 수 없다.
userInput.disabled = true;
sendBtn.disabled = true;
resetBtn.disabled = true;

// 슬라이더 값 표시
tempSlider.oninput = () => {
    tempValue.textContent = tempSlider.value;
};

tokensSlider.oninput = () => {
    tokensValue.textContent = tokensSlider.value;
};

// 페르소나 선택
function selectPersona(personaId) {
    // 클릭한 페르소나를 현재 페르소나로 설정
    currentPersona = personaId;

    document.querySelectorAll(".persona-btn").forEach(btn => {
        btn.classList.toggle(
            "active",
            btn.dataset.persona === personaId
        );
    });

    // 페르소나 선택 후 입력, 전송, 초기화 가능
    userInput.disabled = false;
    sendBtn.disabled = false;
    resetBtn.disabled = false;

    // resetChat()은 비동기 함수이다.
    // 내부의 await fetch()를 만나면 요청이 끝날 때까지 resetChat()이 중단된다.
    // 그동안 selectPersona()의 아래 코드는 계속 실행된다.
    resetChat();

    chatBox.innerHTML = `
        <div class="system-message">
            <strong>
                ${document.querySelector(
                    `[data-persona="${personaId}"] strong`
                ).textContent}
            </strong>
            페르소나로 대화를 시작합니다.
        </div>
    `;

    userInput.focus();
}

// 메시지 추가
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

// 메시지 전송
async function sendMessage() {
    const message = userInput.value.trim();

    // 메시지가 전송되면 안 되는 경우
    // 1. 메시지가 비어 있거나
    // 2. 선택된 페르소나가 없거나
    // 3. 현재 스트리밍 응답을 받고 있는 경우
    if (!message || !currentPersona || isStreaming) return;

    isStreaming = true;

    // 입력한 메시지를 채팅 창에 추가
    appendMessage("user", message);

    // 메시지 전송 중에는 다른 메시지를 전송할 수 없다.
    userInput.value = "";
    userInput.disabled = true;
    sendBtn.disabled = true;

    // LLM 응답을 채울 빈 메시지 요소를 만들고 반환받는다.
    const assistantDiv = appendMessage("assistant", "");

    // 응답이 올 때까지 sendMessage()의 실행을 일시 중단한다.
    const response = await fetch("/chat", {
        method: "POST",

        // JSON 형식의 데이터를 전송한다고 헤더에 표시한다.
        headers: {
            "Content-Type": "application/json"
        },

        // JS 객체를 JSON 문자열로 변환하여 요청 본문에 담는다.
        body: JSON.stringify({
            session_id: sessionId,
            persona: currentPersona,
            model: modelSelect.value,
            message: message,
            temperature: parseFloat(tempSlider.value),
            max_tokens: parseInt(tokensSlider.value)
        })
    });

    // 현재 코드는 SSE 방식으로 응답을 받으므로,
    // response.body에서 Reader 객체를 가져와 스트림을 순차적으로 읽는다.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";

    while (true) {
        // reader.read()는 Promise를 반환한다.
        // 읽기가 완료되면 value에는 바이트 형식의 데이터 조각이 들어간다.
        // done은 스트림이 종료되었는지를 나타낸다.
        const { done, value } = await reader.read();

        if (done) break;

        // 바이트 데이터를 문자열로 변환한다.
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");

        // 마지막 줄은 아직 완성되지 않았을 수 있으므로
        // 다음 데이터와 합치기 위해 buffer에 보관한다.
        buffer = lines.pop();

        for (const line of lines) {
            // SSE의 data 필드가 아닌 줄은 건너뛴다.
            if (!line.startsWith("data: ")) continue;

            // 앞부분의 "data: "를 제거하고 JSON 문자열을 JS 객체로 변환한다.
            const data = JSON.parse(line.slice(6));

            // 전달받은 텍스트를 기존 AI 메시지에 이어 붙인다.
            if (data.text) {
                assistantDiv.querySelector(".text").textContent += data.text;
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            // 응답 생성이 끝나면 토큰 사용량과 소요 시간을 표시한다.
            if (data.finished) {
                tokenInfo.textContent =
                    `입력 ${data.input_tokens}토큰 / ` +
                    `출력 ${data.output_tokens}토큰 / ` +
                    `소요 시간: ${data.elapsed}초`;
            }
        }
    }

    isStreaming = false;

    userInput.disabled = false;
    sendBtn.disabled = false;

    userInput.focus();
}

// 대화 초기화
async function resetChat() {
    // 선택된 페르소나가 없다면 종료
    if (!currentPersona) return;

    await fetch("/reset", {
        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        // 세션, 페르소나, 모델을 요청 본문에 담아 보낸다.
        body: JSON.stringify({
            persona: currentPersona,
            model: modelSelect.value,
            session_id: sessionId
        })
    });

    tokenInfo.textContent = "";
}

// 페르소나 선택 이벤트
document.querySelectorAll(".persona-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        selectPersona(btn.dataset.persona);
    });
});

// 버튼 이벤트
sendBtn.addEventListener("click", sendMessage);
resetBtn.addEventListener("click", resetChat);

// Enter 키로 메시지 전송
userInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});