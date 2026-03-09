"""
=============================================================================
test_samjin.py
=============================================================================
삼진웰텍 OMEGA ROBO K3 연동 테스트 스크립트.

실제 로봇 없이도 MockDeviceClient로 동작 확인 가능.
실제 로봇 연결 시 USE_REAL_ROBOT = True로 변경.
=============================================================================
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from io_interface.device_client import MockDeviceClient, IndyDeviceClient
from welder.samjin_welder import SamjinWelder

# ─────────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────────
USE_REAL_ROBOT = False          # True: 실제 로봇 연결, False: 테스트 모드
ROBOT_IP = "192.168.0.xxx"      # 실제 로봇 IP로 변경


def get_client():
    if USE_REAL_ROBOT:
        client = IndyDeviceClient(robot_ip=ROBOT_IP)
        client.connect()
        return client
    else:
        return MockDeviceClient()


# ─────────────────────────────────────────────────────────────────────
# 테스트 1: 아날로그 변환값 확인
# ─────────────────────────────────────────────────────────────────────
def test_analog_conversion():
    print("\n" + "="*50)
    print("  테스트 1: 아날로그 변환값 확인")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    test_cases = [
        (0,   0),
        (25,  250),
        (50,  500),
        (15,  150),
        (30,  300),
    ]

    print(f"\n  {'전압(V)':>8} {'→ AO(V)':>10}  |  {'전류(A)':>8} {'→ AO(V)':>10}")
    print("  " + "-"*45)
    for v, c in test_cases:
        v_mv = welder._to_ao_mv(v, welder.voltage_min, welder.voltage_max)
        c_mv = welder._to_ao_mv(c, welder.current_min, welder.current_max)
        print(f"  {v:>7}V  →  {v_mv/1000:>6.3f}V  |  {c:>6}A  →  {c_mv/1000:>6.3f}V")


# ─────────────────────────────────────────────────────────────────────
# 테스트 2: 아크 ON/OFF
# ─────────────────────────────────────────────────────────────────────
def test_arc():
    print("\n" + "="*50)
    print("  테스트 2: 아크 ON/OFF")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    print("\n  → 아크 ON (전압 25V, 전류 200A)")
    welder.set_arc(True, voltage=25.0, current=200.0)
    client.print_status()

    import time
    time.sleep(1)

    print("  → 아크 OFF")
    welder.set_arc(False)
    client.print_status()


# ─────────────────────────────────────────────────────────────────────
# 테스트 3: 와이어 인칭
# ─────────────────────────────────────────────────────────────────────
def test_inching():
    print("\n" + "="*50)
    print("  테스트 3: 와이어 인칭")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    print("\n  → 와이어 정방향 1초 피딩")
    welder.inching(direction=0, duration=1.0)

    print("\n  → 와이어 역방향 1초 피딩")
    welder.inching(direction=1, duration=1.0)


# ─────────────────────────────────────────────────────────────────────
# 테스트 4: 터치 센싱
# ─────────────────────────────────────────────────────────────────────
def test_touch_sensing():
    print("\n" + "="*50)
    print("  테스트 4: 터치 센싱")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    print("\n  → 터치 센싱 ON")
    welder.set_touch(True)

    print(f"  → 접촉 여부: {welder.is_touched()}")  # False

    print("\n  → 모재 접촉 시뮬레이션")
    client.simulate_touch(True)
    print(f"  → 접촉 여부: {welder.is_touched()}")  # True

    print("\n  → 터치 센싱 OFF")
    welder.set_touch(False)


# ─────────────────────────────────────────────────────────────────────
# 테스트 5: 전체 용접 시퀀스
# ─────────────────────────────────────────────────────────────────────
def test_weld_sequence():
    print("\n" + "="*50)
    print("  테스트 5: 전체 용접 시퀀스")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    # 전압 25V, 전류 200A, 용접 2초
    welder.weld_sequence(
        voltage=25.0,
        current=200.0,
        weld_time=2.0,
        pre_flow=0.3,
        post_flow=0.5
    )
    client.print_status()


# ─────────────────────────────────────────────────────────────────────
# 테스트 6: 비상 정지
# ─────────────────────────────────────────────────────────────────────
def test_emergency_stop():
    print("\n" + "="*50)
    print("  테스트 6: 비상 정지")
    print("="*50)

    client = MockDeviceClient()
    welder = SamjinWelder(client)

    print("\n  → 용접 중 상태 만들기")
    welder.set_gas(True)
    welder.set_arc(True, voltage=30.0, current=250.0)
    client.print_status()

    print("  → 비상 정지 실행!")
    welder.emergency_stop()
    client.print_status()


# ─────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("삼진웰텍 OMEGA ROBO K3 × 뉴로메카 Indy7 연동 테스트")
    print("="*50)

    test_analog_conversion()
    test_arc()
    test_inching()
    test_touch_sensing()
    test_weld_sequence()
    test_emergency_stop()

    print("\n모든 테스트 완료!")
