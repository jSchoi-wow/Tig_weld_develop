"""
=============================================================================
samjin_welder.py
=============================================================================
삼진웰텍 OMEGA ROBO K3 - 뉴로메카 Indy7 아날로그 연동 핵심 모듈

[신호 구성]
  AO 0번 (VC 단자) ──→ 전압 제어  (0~10V → 0~50V)
  AO 1번 (CC 단자) ──→ 전류 제어  (0~10V → 0~500A)
  DO 1번 (WCR 단자)──→ 아크 ON/OFF
  DO 0번 (TIS 단자)──→ 터치 센싱 ON/OFF
  DO 2번           ──→ 가스 밸브 ON/OFF
  DO 3번           ──→ 피더 정방향 (와이어 나감)
  DO 4번           ──→ 피더 역방향 (와이어 들어감)
  DI 0번           ←── 아크 피드백
  DI 1번           ←── 에러 피드백
  DI 2번 (TIR 단자)←── 터치 센싱 피드백

[아날로그 변환 공식]
  AO 출력(mV) = 설정값 / 최댓값 × 10 × 1000
  예) 25V  → 25/50 × 10000 = 5000mV = 5.0V
  예) 250A → 250/500 × 10000 = 5000mV = 5.0V
=============================================================================
"""

import json
import time
import threading
from pathlib import Path


class SamjinWelder:
    """
    삼진웰텍 OMEGA ROBO K3 제어 클래스.

    device_client: SetDO / SetAO / GetDI 메서드를 가진 I/O 클라이언트
                   (MockDeviceClient 또는 IndyDeviceClient)
    config_path:   config.json 경로 (기본값: 같은 폴더의 config.json)
    """

    def __init__(self, device_client, config_path: str = None):
        self._client = device_client
        self._lock = threading.Lock()

        # 설정 파일 로드
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        # 용접기 스펙
        w = cfg["welder"]
        self.voltage_min = w["voltage_min"]   # 0 V
        self.voltage_max = w["voltage_max"]   # 50 V
        self.current_min = w["current_min"]   # 0 A
        self.current_max = w["current_max"]   # 500 A
        self.ao_min = w["ao_min"]             # 0 V
        self.ao_max = w["ao_max"]             # 10 V

        # 핀 매핑
        p = cfg["pin_map"]
        self.pin_touch_on       = p["DO"]["touch_on"]       # DO 0
        self.pin_arc_on         = p["DO"]["arc_on"]         # DO 1
        self.pin_gas_check      = p["DO"]["gas_check"]      # DO 2
        self.pin_inching_plus   = p["DO"]["inching_plus"]   # DO 3
        self.pin_inching_minus  = p["DO"]["inching_minus"]  # DO 4
        self.pin_arc_feedback   = p["DI"]["arc_feedback"]   # DI 0
        self.pin_welder_error   = p["DI"]["welder_error"]   # DI 1
        self.pin_touch_feedback = p["DI"]["touch_feedback"] # DI 2
        self.pin_ao_voltage     = p["AO"]["voltage"]        # AO 0
        self.pin_ao_current     = p["AO"]["current"]        # AO 1

        # 내부 상태
        self._arc_active = False
        self._gas_active = False
        self._current_voltage = 0.0
        self._current_current = 0.0

        print("[SamjinWelder] 초기화 완료")
        print(f"  전압 범위: {self.voltage_min}~{self.voltage_max}V")
        print(f"  전류 범위: {self.current_min}~{self.current_max}A")

    # =================================================================
    # 아날로그 변환 유틸
    # =================================================================
    def _to_ao_mv(self, value: float, v_min: float, v_max: float) -> float:
        """
        용접기 설정값 → AO 출력 전압(mV) 변환.

        value:  사용자가 설정한 값 (전압V 또는 전류A)
        v_min:  입력 최솟값
        v_max:  입력 최댓값
        반환:   mV 단위 (예: 5000 = 5.0V)
        """
        value = min(max(value, v_min), v_max)  # 클램핑
        ratio = (value - v_min) / (v_max - v_min) if v_max != v_min else 0
        return ratio * (self.ao_max - self.ao_min) * 1000  # mV

    # =================================================================
    # 아크(용접) ON/OFF + 전압/전류 설정
    # =================================================================
    def set_arc(self, active: bool, voltage: float = None, current: float = None) -> bool:
        """
        아크(용접) ON/OFF 및 전압/전류 설정.

        active:  True=용접 시작, False=용접 정지
        voltage: 용접 전압 (V), 0~50V
        current: 용접 전류 (A), 0~500A

        [신호 순서 - 아크 ON]
          1. AO 0번 (VC) → 전압값 출력
          2. AO 1번 (CC) → 전류값 출력
          3. DO 1번 (WCR) → HIGH (아크 시작)

        [신호 순서 - 아크 OFF]
          1. DO 1번 (WCR) → LOW (아크 정지)
          2. AO 0번, 1번 → 0V (안전하게 초기화)
        """
        with self._lock:
            print(f"\n[set_arc] {'ON' if active else 'OFF'}"
                  + (f" | {voltage}V, {current}A" if active else ""))

            ao_list = []

            if active:
                if voltage is None or current is None:
                    print("  [오류] 아크 ON 시 voltage, current 필수")
                    return False

                # 전압/전류 값 저장
                self._current_voltage = voltage
                self._current_current = current

                # 아날로그 변환
                v_mv = self._to_ao_mv(voltage, self.voltage_min, self.voltage_max)
                c_mv = self._to_ao_mv(current, self.current_min, self.current_max)

                # 1. AO 출력 (전압/전류 먼저 설정)
                ao_list.append({"address": self.pin_ao_voltage, "voltage": v_mv})
                ao_list.append({"address": self.pin_ao_current, "voltage": c_mv})
                self._client.SetAO(ao_list)

                # 2. 아크 ON 신호
                time.sleep(0.05)  # AO 안정화 대기 (50ms)
                self._client.SetDO([{"address": self.pin_arc_on, "state": 1}])
                self._arc_active = True

            else:
                # 1. 아크 OFF 신호 먼저
                self._client.SetDO([{"address": self.pin_arc_on, "state": 0}])

                # 2. AO 0으로 초기화
                ao_list.append({"address": self.pin_ao_voltage, "voltage": 0})
                ao_list.append({"address": self.pin_ao_current, "voltage": 0})
                self._client.SetAO(ao_list)
                self._arc_active = False
                self._current_voltage = 0.0
                self._current_current = 0.0

        return True

    # =================================================================
    # 가스 밸브 ON/OFF
    # =================================================================
    def set_gas(self, active: bool) -> bool:
        """
        보호 가스 밸브 ON/OFF.
        active: True=가스 열림, False=가스 닫힘

        [일반적인 용접 순서]
          가스 ON → (pre-flow 대기) → 아크 ON → 용접 → 아크 OFF → (post-flow 대기) → 가스 OFF
        """
        with self._lock:
            state = 1 if active else 0
            print(f"\n[set_gas] {'ON' if active else 'OFF'}")
            self._client.SetDO([{"address": self.pin_gas_check, "state": state}])
            self._gas_active = active
        return True

    # =================================================================
    # 와이어 피더(인칭) 제어
    # =================================================================
    def set_inching(self, active: bool, direction: int) -> bool:
        """
        와이어 피더 수동 제어 (인칭).

        active:    True=동작, False=정지
        direction: 0=정방향(와이어 나감), 1=역방향(와이어 들어감)

        DO 3번 = 정방향, DO 4번 = 역방향
        """
        with self._lock:
            dir_str = "정방향(나감)" if direction == 0 else "역방향(들어감)"
            print(f"\n[set_inching] {'ON' if active else 'OFF'} | {dir_str}")

            if active:
                if direction == 0:
                    # 정방향: DO3 ON, DO4 OFF
                    self._client.SetDO([
                        {"address": self.pin_inching_plus,  "state": 1},
                        {"address": self.pin_inching_minus, "state": 0},
                    ])
                else:
                    # 역방향: DO3 OFF, DO4 ON
                    self._client.SetDO([
                        {"address": self.pin_inching_plus,  "state": 0},
                        {"address": self.pin_inching_minus, "state": 1},
                    ])
            else:
                # 정지: DO3 OFF, DO4 OFF
                self._client.SetDO([
                    {"address": self.pin_inching_plus,  "state": 0},
                    {"address": self.pin_inching_minus, "state": 0},
                ])
        return True

    def inching(self, direction: int, duration: float) -> bool:
        """
        와이어 인칭을 지정한 시간(초)만큼 실행 후 자동 정지.

        direction: 0=정방향, 1=역방향
        duration:  동작 시간 (초)

        사용예) welder.inching(0, 2.0) → 2초간 와이어 전진
        """
        self.set_inching(True, direction)
        time.sleep(duration)
        self.set_inching(False, direction)
        return True

    # =================================================================
    # 터치 센싱 제어 (용접 시작점 탐색)
    # =================================================================
    def set_touch(self, active: bool) -> bool:
        """
        터치 센싱 ON/OFF.
        와이어가 모재에 닿았는지 감지하여 용접 시작점을 찾는 기능.

        active: True=터치센싱 시작, False=터치센싱 종료
        """
        with self._lock:
            state = 1 if active else 0
            print(f"\n[set_touch] {'ON' if active else 'OFF'}")
            self._client.SetDO([{"address": self.pin_touch_on, "state": state}])
        return True

    def is_touched(self) -> bool:
        """
        터치 센싱 결과 확인.
        반환: True=와이어가 모재에 접촉됨, False=미접촉

        DI 2번 (TIR 단자) 상태를 읽어서 판단.
        """
        io_data = self._client.GetDI()
        for di in io_data["di"]:
            if di["address"] == self.pin_touch_feedback:
                return di["state"] == 1
        return False

    # =================================================================
    # 상태 피드백 읽기
    # =================================================================
    def is_arc_on(self) -> bool:
        """아크 피드백 확인 (DI 0번)"""
        io_data = self._client.GetDI()
        for di in io_data["di"]:
            if di["address"] == self.pin_arc_feedback:
                return di["state"] == 1
        return False

    def is_error(self) -> bool:
        """용접기 에러 상태 확인 (DI 1번)"""
        io_data = self._client.GetDI()
        for di in io_data["di"]:
            if di["address"] == self.pin_welder_error:
                return di["state"] == 1
        return False

    # =================================================================
    # 전체 비상 정지
    # =================================================================
    def emergency_stop(self):
        """
        비상 정지: 모든 출력을 즉시 OFF.
        아크, 가스, 피더 전부 정지.
        """
        print("\n[비상정지] 모든 출력 OFF!")
        self._client.SetDO([
            {"address": self.pin_arc_on,        "state": 0},
            {"address": self.pin_gas_check,     "state": 0},
            {"address": self.pin_touch_on,      "state": 0},
            {"address": self.pin_inching_plus,  "state": 0},
            {"address": self.pin_inching_minus, "state": 0},
        ])
        self._client.SetAO([
            {"address": self.pin_ao_voltage, "voltage": 0},
            {"address": self.pin_ao_current, "voltage": 0},
        ])
        self._arc_active = False
        self._gas_active = False

    # =================================================================
    # 완전한 용접 시퀀스 (가스 pre-flow 포함)
    # =================================================================
    def weld_sequence(self,
                      voltage: float,
                      current: float,
                      weld_time: float,
                      pre_flow: float = 0.3,
                      post_flow: float = 0.5) -> bool:
        """
        표준 CO2 용접 시퀀스 실행.

        [순서]
          1. 가스 ON (pre_flow 초 대기)
          2. 아크 ON (voltage, current 설정)
          3. weld_time 초 용접 유지
          4. 아크 OFF
          5. 가스 유지 (post_flow 초 대기)
          6. 가스 OFF

        voltage:   용접 전압 (V), 0~50
        current:   용접 전류 (A), 0~500
        weld_time: 용접 시간 (초)
        pre_flow:  가스 선행 공급 시간 (초, 기본 0.3)
        post_flow: 가스 후행 공급 시간 (초, 기본 0.5)
        """
        print(f"\n{'='*50}")
        print(f"  용접 시퀀스 시작")
        print(f"  전압={voltage}V, 전류={current}A, 시간={weld_time}s")
        print(f"{'='*50}")

        try:
            # 1. 가스 ON
            self.set_gas(True)
            print(f"  가스 pre-flow 대기 ({pre_flow}s)...")
            time.sleep(pre_flow)

            # 2. 아크 ON
            self.set_arc(True, voltage=voltage, current=current)
            print(f"  용접 중... ({weld_time}s)")
            time.sleep(weld_time)

            # 3. 아크 OFF
            self.set_arc(False)

            # 4. 가스 post-flow
            print(f"  가스 post-flow 대기 ({post_flow}s)...")
            time.sleep(post_flow)

            # 5. 가스 OFF
            self.set_gas(False)

            print("  용접 시퀀스 완료!")
            return True

        except Exception as e:
            print(f"  [오류] 용접 중 예외 발생: {e}")
            self.emergency_stop()
            return False
