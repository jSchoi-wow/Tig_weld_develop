"""
=============================================================================
main.py - 삼진웰텍 OMEGA ROBO K3 × 뉴로메카 Indy7 연동 메인
=============================================================================

[실행 방법]
  테스트 모드 (로봇 없이):
      python main.py

  실제 로봇 연결:
      python main.py --real --ip 192.168.0.xxx

[전체 구조]
  main.py
  ├── welder/
  │   ├── config.json        ← 핀 번호, 전압/전류 범위 설정
  │   └── samjin_welder.py   ← 삼진 용접기 제어 핵심 클래스
  ├── io_interface/
  │   └── device_client.py   ← 로봇 I/O 통신 클라이언트
  └── test/
      └── test_samjin.py     ← 테스트 스크립트
=============================================================================
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from io_interface.device_client import MockDeviceClient, IndyDeviceClient
from welder.samjin_welder import SamjinWelder


def main():
    parser = argparse.ArgumentParser(description="삼진웰텍 × 뉴로메카 용접 연동")
    parser.add_argument("--real", action="store_true", help="실제 로봇 연결")
    parser.add_argument("--ip", type=str, default="192.168.0.xxx", help="로봇 IP")
    args = parser.parse_args()

    # ── 클라이언트 초기화 ──
    if args.real:
        print(f"실제 로봇 연결 중: {args.ip}")
        client = IndyDeviceClient(robot_ip=args.ip)
        client.connect()
    else:
        print("테스트 모드 (MockDeviceClient)")
        client = MockDeviceClient()

    # ── 용접기 초기화 ──
    welder = SamjinWelder(client)

    # ── 예시: 용접 시퀀스 실행 ──
    try:
        # 1. 와이어 인칭으로 시작 전 준비
        print("\n[1단계] 와이어 준비 (0.5초 피딩)")
        welder.inching(direction=0, duration=0.5)

        # 2. 터치 센싱으로 모재 위치 확인
        print("\n[2단계] 터치 센싱")
        welder.set_touch(True)
        # 실제 환경: 로봇이 천천히 이동하면서 is_touched()가 True 될 때까지 대기
        # while not welder.is_touched():
        #     time.sleep(0.01)
        welder.set_touch(False)

        # 3. 용접 실행 (25V, 200A, 3초)
        print("\n[3단계] 용접 실행")
        welder.weld_sequence(
            voltage=25.0,
            current=200.0,
            weld_time=3.0,
            pre_flow=0.3,
            post_flow=0.5
        )

        print("\n완료!")

    except KeyboardInterrupt:
        print("\n[중단] 비상 정지 실행")
        welder.emergency_stop()

    finally:
        if args.real:
            client.disconnect()


if __name__ == "__main__":
    main()
