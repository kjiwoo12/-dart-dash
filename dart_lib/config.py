import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY")

BASE_URL = "https://opendart.fss.or.kr/api"
REPRT_CODE_ANNUAL = "11011"
FS_DIV_CONSOLIDATED = "CFS"

# Vercel 서버리스 환경은 프로젝트 디렉토리가 읽기 전용이라 /tmp만 쓰기 가능
CORP_CODE_CACHE_PATH = (
    os.path.join(tempfile.gettempdir(), "CORPCODE.xml")
    if os.getenv("VERCEL")
    else "cache/CORPCODE.xml"
)
CORP_CODE_CACHE_MAX_AGE_DAYS = 7

OUTPUT_DIR = "output"

if not DART_API_KEY:
    raise SystemExit(
        "[오류] .env 파일에 DART_API_KEY를 설정해주세요. .env.example 파일을 참고하세요."
    )
