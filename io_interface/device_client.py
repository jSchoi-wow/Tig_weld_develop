"""
=============================================================================
device_client.py
=============================================================================
뉴로메카 Indy7 로봇의 I/O 보드와 통신하는 클라이언트.

실제 환경: IndyDeployment의 gRPC 기반 DeviceSocketClient를 사용
개발/테스트: 이 파일의 MockDeviceClient를 사용 (실제 로봇 없이 테스트 가능)

사용법:
    실제 로봇 연결 시:
        from indydcp.client.robot_client import RobotClient
        robot = RobotClient(robot_ip, name)
        device_client = robot  # SetDO / SetAO / GetDI 지원

    개발/테스트 시:
        from io_interface.device_client import MockDeviceClient
        device_client = MockDeviceClient()
=============================================================================
"""

import time


class MockDeviceClient:
    """
    실제 로봇 없이 개발/테스트용으로 사용하는 가짜 I/O 클라이언트.
    SetDO / SetAO / GetDI 호출 결과를 콘솔에 출력한다.
    """

    def __init__(self):
        self._do_state = {}   # DO 핀 상태 저장 {address: state}
        self._ao_state = {}   # AO 핀 상태 저장 {address: voltage_mv}
        self._di_state = {    # DI 핀 상태 (테스트용 초기값)
            0: 0,  # arc_feedback: OFF
            1: 0,  # welder_error: 정상
            2: 0,  # touch_feedback: 미접촉
        }
        print("[MockDeviceClient] 초기화 완료 (테스트 모드)")

    # ─────────────────────────────────────────────────────────────────
    # DO (디지털 출력) 제어
    # ─────────────────────────────────────────────────────────────────
    def SetDO(self, do_list: list):
        """
        디지털 출력 설정.
        do_list: [{"address": 핀번호, "state": 0or1}, ...]
        """
        for do in do_list:
            addr = do['address']
            state = do['state']
            self._do_state[addr] = state
            label = "ON " if state == 1 else "OFF"
            print(f"  [DO {addr:2d}] {label}  ← {self._get_do_label(addr)}")

    def SetEndDO(self, do_list: list):
        """엔드툴 DO (동일하게 처리)"""
        self.SetDO(do_list)

    # ─────────────────────────────────────────────────────────────────
    # AO (아날로그 출력) 제어
    # ─────────────────────────────────────────────────────────────────
    def SetAO(self, ao_list: list):
        """
        아날로그 출력 설정.
        ao_list: [{"address": 핀번호, "voltage": mV값}, ...]
        """
        for ao in ao_list:
            addr = ao['address']
            voltage_mv = ao['voltage']
            voltage_v = voltage_mv / 1000.0
            self._ao_state[addr] = voltage_mv
            print(f"  [AO {addr:2d}] {voltage_v:.3f}V ({voltage_mv:.0f}mV)  ← {self._get_ao_label(addr)}")

    def SetEndAO(self, ao_list: list):
        """엔드툴 AO (동일하게 처리)"""
        self.SetAO(ao_list)

    # ─────────────────────────────────────────────────────────────────
    # DI (디지털 입력) 읽기
    # ─────────────────────────────────────────────────────────────────
    def GetDI(self) -> dict:
        """
        디지털 입력 상태 반환.
        반환: {"di": [{"address": 핀번호, "state": 0or1}, ...]}
        """
        di_list = [{"address": addr, "state": state}
                   for addr, state in self._di_state.items()]
        return {"di": di_list}

    def simulate_touch(self, touched: bool):
        """테스트용: 터치 센싱 피드백 시뮬레이션"""
        self._di_state[2] = 1 if touched else 0
        print(f"  [시뮬레이션] 터치 피드백: {'접촉됨' if touched else '미접촉'}")

    def simulate_arc_feedback(self, arc_on: bool):
        """테스트용: 아크 피드백 시뮬레이션"""
        self._di_state[0] = 1 if arc_on else 0
        print(f"  [시뮬레이션] 아크 피드백: {'아크 ON' if arc_on else '아크 OFF'}")

    def simulate_error(self, error: bool):
        """테스트용: 에러 신호 시뮬레이션"""
        self._di_state[1] = 1 if error else 0
        print(f"  [시뮬레이션] 에러 상태: {'에러 발생!' if error else '정상'}")

    # ─────────────────────────────────────────────────────────────────
    # 현재 상태 출력
    # ─────────────────────────────────────────────────────────────────
    def print_status(self):
        print("\n" + "="*50)
        print("  현재 I/O 상태")
        print("="*50)
        for addr in sorted(self._do_state):
            state = "ON " if self._do_state[addr] == 1 else "OFF"
            print(f"  DO {addr:2d}: {state}  ({self._get_do_label(addr)})")
        for addr in sorted(self._ao_state):
            v = self._ao_state[addr] / 1000.0
            print(f"  AO {addr:2d}: {v:.3f}V  ({self._get_ao_label(addr)})")
        for addr in sorted(self._di_state):
            state = "ON " if self._di_state[addr] == 1 else "OFF"
            print(f"  DI {addr:2d}: {state}  ({self._get_di_label(addr)})")
        print("="*50 + "\n")

    def _get_do_label(self, addr):
        labels = {0: "터치센싱(TIS)", 1: "아크ON(WCR)", 2: "가스밸브",
                  3: "피더 정방향", 4: "피더 역방향"}
        return labels.get(addr, f"DO_{addr}")

    def _get_ao_label(self, addr):
        labels = {0: "전압제어(VC)", 1: "전류제어(CC)"}
        return labels.get(addr, f"AO_{addr}")

    def _get_di_label(self, addr):
        labels = {0: "아크피드백", 1: "에러피드백", 2: "터치피드백(TIR)"}
        return labels.get(addr, f"DI_{addr}")


class IndyDeviceClient:
    """
    실제 뉴로메카 Indy7 로봇 연결용 클라이언트 래퍼.
    IndyDCP 또는 gRPC 클라이언트를 감싸서 통일된 인터페이스 제공.

    사용법:
        client = IndyDeviceClient(robot_ip="192.168.0.xxx")
        client.connect()
    """

    def __init__(self, robot_ip: str, robot_name: str = "NRMK-Indy7"):
        self.robot_ip = robot_ip
        self.robot_name = robot_name
        self._client = None

    def connect(self):
        """로봇에 연결 (IndyDCP 사용)"""
        try:
            # IndyDCP v2 기준
            import indydcp
            self._client = indydcp.client.RobotClient(self.robot_ip, self.robot_name)
            self._client.connect()
            print(f"[IndyDeviceClient] 연결 성공: {self.robot_ip}")
        except ImportError:
            raise RuntimeError(
                "IndyDCP 라이브러리가 없습니다.\n"
                "설치: pip install indydcp\n"
                "또는 뉴로메카에서 제공하는 PythonMiddleware 사용"
            )

    def SetDO(self, do_list: list):
        for do in do_list:
            self._client.set_do(do['address'], do['state'])

    def SetAO(self, ao_list: list):
        for ao in ao_list:
            # voltage는 mV 단위 → V로 변환 후 전송
            self._client.set_ao(ao['address'], ao['voltage'] / 1000.0)

    def GetDI(self) -> dict:
        di_raw = self._client.get_di()
        di_list = [{"address": i, "state": v} for i, v in enumerate(di_raw)]
        return {"di": di_list}

    def disconnect(self):
        if self._client:
            self._client.disconnect()
            print("[IndyDeviceClient] 연결 해제")
