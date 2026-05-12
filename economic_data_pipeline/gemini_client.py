# gemini_client.py
# Google Gemini AI를 이용한 IR 자료 한국어 요약
import time
import logging
from config import GEMINI_KEY

logger = logging.getLogger(__name__)

# 무료 티어 사용 가능 모델 (순서대로 폴백)
GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]
RPM_SLEEP = 4.5   # 15 RPM 제한 준수


def summarize_ir(company: str, date: str, text: str) -> str:
    """
    IR 자료(8-K HTML 텍스트)를 한국어 투자자 관점으로 요약
    Returns: 요약 문자열 (실패 시 오류 메시지)
    """
    if not GEMINI_KEY:
        return "❌ GEMINI_API_KEY 미설정"
    if not text.strip():
        return "❌ 문서 내용 없음"

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        return f"❌ Gemini 클라이언트 초기화 실패: {e}"

    prompt = f"""다음은 {company}({date})의 SEC 8-K 공시 내용입니다.
한국 주식 투자자를 위한 핵심 요약을 작성해주세요.

[요약 항목]
1. 📊 실적 핵심 (매출, 영업이익, EPS 등 주요 수치)
2. ☁️ 클라우드/AI 사업 현황 및 성장률
3. 💰 CapEx 투자 규모 및 계획
4. 📈 가이던스 (다음 분기 전망)
5. ⚠️ 주요 리스크 및 주의사항

각 항목을 2-3줄 이내로 간결하게 작성하고, 수치는 반드시 포함해주세요.
실적 관련 수치가 없으면 "공시에 수치 미포함"으로 표기해주세요.

[원문]
{text}
"""

    last_error = ""
    for model in GEMINI_MODELS:
        for attempt in range(2):   # 모델당 최대 2회 재시도
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                time.sleep(RPM_SLEEP)
                logger.info(f"[Gemini] 요약 성공 (model={model}, {company} {date})")
                return resp.text.strip()
            except Exception as e:
                err = str(e)
                last_error = err
                if "429" in err:
                    logger.warning(f"[Gemini] {model} 요청 한도 초과 - 다음 모델로 폴백")
                    break   # 다음 모델로 즉시 이동
                elif "503" in err:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"[Gemini] {model} 서버 부하 (503) - {wait}s 대기 후 재시도")
                    time.sleep(wait)
                else:
                    logger.error(f"[Gemini] {model} 오류: {err[:80]}")
                    break   # 비율 한도 외 오류는 다음 모델로

    logger.error(f"[Gemini] 모든 모델 실패 ({company} {date}): {last_error[:80]}")
    if "429" in last_error:
        return "⏳ Gemini API 요청 한도 초과 - 잠시 후 재시도 필요"
    return f"❌ 요약 실패: {last_error[:80]}"

