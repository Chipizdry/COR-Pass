# import serial
# import serial.tools.list_ports
# import time


# def pick_port():
#     ports = list(serial.tools.list_ports.comports())
#     print("Порты:")
#     for i, p in enumerate(ports, 1):
#         print(f"{i}. {p.device} - {p.description}")
#     idx = int(input("Выберите порт: "))
#     return ports[idx - 1].device


# def send(cmd, ser):
#     ser.write((cmd + "\r").encode())
#     time.sleep(0.2)
#     raw = ser.read_until(b"\r")
#     return raw


# def get_inverter_info(ser):
#     """
#     Получение информации об инверторе
#     """
#     info = {}
    
#     # Пробуем получить модель через QMN
#     raw = send("QMN", ser)
#     if not raw.startswith(b"(NAK"):
#         info["model"] = raw[1:-3].decode(errors="ignore").strip()
#     else:
#         # Если QMN не работает, определяем модель по параметрам из QPIRI
#         raw = send("QPIRI", ser)
#         if raw.startswith(b"("):
#             body = raw[1:-3].decode(errors="ignore").strip()
#             parts = body.split()
#             if len(parts) > 6:
#                 power = int(parts[6])
#                 info["model"] = f"MKS2-{power}"
    
#     # Пробуем получить серийный номер через QID
#     raw = send("QID", ser)
#     if not raw.startswith(b"(NAK"):
#         info["serial"] = raw[1:-3].decode(errors="ignore").strip()
#     else:
#         info["serial"] = "Не доступен"
    
#     return info


def parse_qpiri(raw: bytes):
    """
    Парсер для QPIRI - параметры инвертора
    """
    if not raw.startswith(b"("):
        return {"error": "invalid response", "raw": raw}

    body = raw[1:-3].decode(errors="ignore").strip()
    parts = body.split()

    try:
        return {
            "grid_rating_voltage": float(parts[0]),
            "grid_rating_current": float(parts[1]),
            "ac_output_rating_voltage": float(parts[2]),
            "ac_output_rating_freq": float(parts[3]),
            "ac_output_rating_current": float(parts[4]),
            "ac_output_rating_apparent_power": int(parts[5]),
            "ac_output_rating_active_power": int(parts[6]),
            "battery_rating_voltage": float(parts[7]),
            "battery_recharge_voltage": float(parts[8]),
            "battery_under_voltage": float(parts[9]),
            "battery_bulk_voltage": float(parts[10]),
            "battery_float_voltage": float(parts[11]),
            "battery_type": int(parts[12]),
            "max_ac_charging_current": int(parts[13]),
            "max_charging_current": int(parts[14]),
            "input_voltage_range": int(parts[15]),
            "output_source_priority": int(parts[16]),
            "charger_source_priority": int(parts[17]),
            "parallel_max_num": int(parts[18]),
            "machine_type": int(parts[19]),
            "topology": int(parts[20]),
            "output_mode": int(parts[21]),
            "battery_recharge_voltage_2": float(parts[22]),
            "pv_ok_condition": int(parts[23]),
            "pv_power_balance": int(parts[24]),
            "max_parallel_num": int(parts[25]) if len(parts) > 25 else 0,
            "max_charger_current": int(parts[26]) if len(parts) > 26 else 0,
        }
    except Exception as e:
        return {"error": str(e), "raw": raw, "parts": parts}


def parse_qpigs(raw: bytes):
    """
    Парсер для QPIGS - основные данные
    """
    if not raw.startswith(b"("):
        return {"error": "invalid response", "raw": raw}

    body = raw[1:-3].decode(errors="ignore").strip()
    parts = body.split()

    try:
        data = {
            "grid_voltage": float(parts[0]),
            "grid_frequency": float(parts[1]),
            "ac_output_voltage": float(parts[2]),
            "ac_output_frequency": float(parts[3]),
            "ac_output_apparent_power": int(parts[4]),
            "ac_output_active_power": int(parts[5]),
            "output_load_percent": int(parts[6]),
            "bus_voltage": int(parts[7]),
            "battery_voltage": float(parts[8]),
            "battery_charging_current": int(parts[9]),
            "battery_capacity": int(parts[10]),
            "inverter_heat_sink_temperature": int(parts[11]),
            "pv_input_current": float(parts[12]),
            "pv_input_voltage": float(parts[13]),
            "battery_voltage_scc": float(parts[14]),
            "battery_discharge_current": int(parts[15]),
            "device_status": parts[16],
            "ac_output_power": int(parts[17]) if len(parts) > 17 else 0,
            "ac_output_load_percent": int(parts[18]) if len(parts) > 18 else 0,
        }
        
        # Расшифровка статуса устройства
        status_bits = parts[16]
        if len(status_bits) >= 8:
            data["status_decoded"] = {
                "add_sbu_priority_version": status_bits[0],
                "configuration_status": status_bits[1],
                "scc_firmware_version": status_bits[2],
                "load_status": status_bits[3],
                "battery_voltage_status": status_bits[4],
                "charging_status": status_bits[5:8]
            }
        
        return data
    except Exception as e:
        return {"error": str(e), "raw": raw, "parts": parts}

def parse_qflag(raw: bytes):
    """
    Парсер для QFLAG - статус флагов
    """
    if not raw.startswith(b"("):
        return {"error": "invalid response", "raw": raw}

    body = raw[1:-3].decode(errors="ignore").strip()
    
    # Анализируем строку разными способами
    
    result = {
        "raw_string": body,
        "length": len(body),
        "hex_representation": body.encode().hex(),
        "ascii_codes": [ord(c) for c in body]
    }
    
    # Попытка интерпретации как битовой маски
    bit_analysis = {}
    for i, char in enumerate(body):
        bit_analysis[f"char_{i}"] = {
            "character": char,
            "ascii_code": ord(char),
            "binary": bin(ord(char))[2:].zfill(8)
        }
    
    result["bit_analysis"] = bit_analysis
    
    # Попытка расшифровки как кодов состояний
    flag_interpretation = {
        'E': "Enable/Error",
        'a': "AC input",
        'k': "Battery status", 
        'u': "Utility",
        'v': "Voltage",
        'x': "Unknown X",
        'y': "Unknown Y",
        'z': "Unknown Z",
        'D': "DC/Discharge",
        'b': "Battery",
        'j': "Junction",
        'l': "Load",
        'n': "Notification"
    }
    
    decoded_flags = {}
    for char in body:
        decoded_flags[char] = flag_interpretation.get(char, "Unknown")
    
    result["decoded_flags"] = decoded_flags
    
    # Альтернативная интерпретация - как единая битовая маска
    if len(body) >= 8:
        # Предполагаем, что это 8-битная маска
        binary_string = ''.join([bin(ord(c))[2:].zfill(8) for c in body[:8]])
        result["combined_binary"] = binary_string
        
        # Попробуем стандартную интерпретацию флагов MKS серии
        standard_flags = {
            "buzzer": binary_string[0] if len(binary_string) > 0 else "0",
            "overload_bypass": binary_string[1] if len(binary_string) > 1 else "0",
            "power_saving": binary_string[2] if len(binary_string) > 2 else "0",
            "lcd_timeout": binary_string[3] if len(binary_string) > 3 else "0",
            "overload_restart": binary_string[4] if len(binary_string) > 4 else "0",
            "overtemp_restart": binary_string[5] if len(binary_string) > 5 else "0",
            "backlight": binary_string[6] if len(binary_string) > 6 else "0",
            "alarm": binary_string[7] if len(binary_string) > 7 else "0",
            "fault_record": binary_string[8] if len(binary_string) > 8 else "0",
            "primary_source_interrupt": binary_string[9] if len(binary_string) > 9 else "0",
        }
        result["standard_flags"] = standard_flags
    
    return result

def parse_qpiws(raw: bytes):
    """
    Парсер для QPIWS - предупреждения
    """
    if not raw.startswith(b"("):
        return {"error": "invalid response", "raw": raw}

    body = raw[1:-3].decode(errors="ignore").strip()
    
    if len(body) >= 36:
        warnings = {
            "inverter_fault": body[0],
            "bus_over": body[1],
            "bus_under": body[2],
            "bus_soft_fail": body[3],
            "line_fail": body[4],
            "opv_short": body[5],
            "over_temperature": body[6],
            "fan_locked": body[7],
            "battery_voltage_high": body[8],
            "battery_low_alarm": body[9],
            "reserved1": body[10],
            "battery_under_shutdown": body[11],
            "reserved2": body[12],
            "overload": body[13],
            "eeprom_fault": body[14],
            "inverter_over_current": body[15],
            "inverter_soft_fail": body[16],
            "self_test_fail": body[17],
            "op_dc_voltage_over": body[18],
            "bat_open": body[19],
            "current_sensor_fail": body[20],
            "battery_short": body[21],
            "power_limit": body[22],
            "pv_voltage_high": body[23],
            "mppt_overload_fault": body[24],
            "mppt_overload_warning": body[25],
            "battery_too_low_to_charge": body[26],
        }
        return warnings
    else:
        return {"error": "warning string too short", "raw": body}


def parse_qpigs2(raw: bytes):
    """
    Парсер для QPIGS2 - дополнительные данные PV2
    """
    if not raw.startswith(b"("):
        return {"error": "invalid response", "raw": raw}

    body = raw[1:-3].decode(errors="ignore").strip()
    parts = body.split()

    try:
        return {
            "pv2_input_voltage": float(parts[0]),
            "pv2_input_frequency": float(parts[1]),
            "pv2_input_current": float(parts[2]),
            "unknown1": float(parts[3]),
            "pv2_input_power": int(parts[4]),
            "unknown2": int(parts[5]),
            "unknown3": int(parts[6]),
            "unknown4": int(parts[7]),
            "unknown5": float(parts[8]),
            "unknown6": int(parts[9]),
            "unknown7": int(parts[10]),
            "unknown8": int(parts[11]),
            "unknown9": float(parts[12]),
            "unknown10": float(parts[13]),
            "unknown11": float(parts[14]),
            "unknown12": int(parts[15]),
            "device_status_2": parts[16],
            "unknown13": parts[17],
            "unknown14": parts[18],
            "unknown15": int(parts[19]),
            "unknown16": int(parts[20]),
        }
    except Exception as e:
        return {"error": str(e), "raw": raw, "parts": parts}


def main():
    # port = pick_port()
    # ser = serial.Serial(port, 2400, timeout=1)
    # print(f"Подключено к {port}")
    
    # # Получаем информацию об инверторе при подключении
    # print("Получение информации об инверторе...")
    # info = get_inverter_info(ser)
    print("="*50)
    print("ИНФОРМАЦИЯ ОБ ИНВЕРТОРЕ:")
    # print(f"Модель: {info.get('model', 'Не определено')}")
    # print(f"Серийный номер: {info.get('serial', 'Не доступен')}")
    print("="*50)

    while True:
        print("\n" + "="*50)
        print("КОМАНДЫ ДЛЯ ИНВЕРТОРА:")
        print("1 — QPIRI (параметры инвертора) - РАБОТАЕТ")
        print("2 — QPIGS (основные данные) - РАБОТАЕТ")
        print("3 — QPIWS (предупреждения) - РАБОТАЕТ")
        print("4 — QPIGS2 (доп. данные PV2) - РАБОТАЕТ")
        print("5 — Попробовать QMOD")
        print("6 — QID (серийный номер) - РАБОТАЕТ")
        print("7 — QMN (модель) - РАБОТАЕТ")
        print("8 — QDI (настройки инвертора) - РАБОТАЕТ")
        print("9 — Попробовать QFLAG")
        print("0 — Выход")

        choice = input(">>> ")

        # if choice == "0":
        #     ser.close()
        #     break

        # elif choice == "1":
        #     print("Запрос параметров QPIRI...")
        #     raw = send("QPIRI", ser)
        #     print("RAW:", raw)
        #     parsed = parse_qpiri(raw)
        #     if "error" not in parsed:
        #         print("ПАРАМЕТРЫ ИНВЕРТОРА:")
        #         for key, value in parsed.items():
        #             print(f"  {key}: {value}")
        #     else:
        #         print("Ошибка парсинга QPIRI")

        # elif choice == "2":
        #     print("Запрос основных данных QPIGS...")
        #     raw = send("QPIGS", ser)
        #     print("RAW:", raw)
        #     parsed = parse_qpigs(raw)
        #     if "error" not in parsed:
        #         print("ОСНОВНЫЕ ДАННЫЕ:")
        #         for key, value in parsed.items():
        #             if key != "status_decoded":
        #                 print(f"  {key}: {value}")
                
        #         if "status_decoded" in parsed:
        #             print("\n  СТАТУС УСТРОЙСТВА:")
        #             for key, value in parsed["status_decoded"].items():
        #                 print(f"    {key}: {value}")
        #     else:
        #         print("Ошибка парсинга QPIGS")

        # elif choice == "3":
        #     print("Запрос предупреждений QPIWS...")
        #     raw = send("QPIWS", ser)
        #     print("RAW:", raw)
        #     parsed = parse_qpiws(raw)
        #     if "error" not in parsed:
        #         print("ПРЕДУПРЕЖДЕНИЯ:")
        #         active_warnings = False
        #         for key, value in parsed.items():
        #             if value == "1":
        #                 print(f"  ⚠️  {key}: АКТИВНО")
        #                 active_warnings = True
        #         if not active_warnings:
        #             print("  ✅ Нет активных предупреждений")
        #     else:
        #         print("Ошибка парсинга QPIWS")

        # elif choice == "4":
        #     print("Запрос дополнительных данных QPIGS2...")
        #     raw = send("QPIGS2", ser)
        #     print("RAW:", raw)
        #     parsed = parse_qpigs2(raw)
        #     if "error" not in parsed:
        #         print("ДАННЫЕ PV2:")
        #         for key, value in parsed.items():
        #             print(f"  {key}: {value}")
        #     else:
        #         print("Ошибка парсинга QPIGS2")

        # elif choice == "5":
        #     print("Попытка QMOD...")
        #     raw = send("QMOD", ser)
        #     print("RAW:", raw)

        # elif choice == "6":
        #     print("Попытка QID...")
        #     raw = send("QID", ser)
        #     print("RAW:", raw)

        # elif choice == "7":
        #     print("Попытка QMN...")
        #     raw = send("QMN", ser)
        #     print("RAW:", raw)

        # elif choice == "8":
        #     print("Попытка QDI...")
        #     raw = send("QDI", ser)
        #     print("RAW:", raw)

        # elif choice == "9":
        #     print("Попытка QFLAG...")
        #     raw = send("QFLAG", ser)
        #     print("RAW:", raw)
        #     # Вызываем парсер флагов
        #     parsed = parse_qflag(raw)
        #     if "error" not in parsed:
        #         print("\n" + "="*50)
        #         print("АНАЛИЗ ФЛАГОВ QFLAG:")
        #         print(f"Сырая строка: {parsed['raw_string']}")
        #         print(f"Длина: {parsed['length']} символов")
        #         print(f"HEX: {parsed['hex_representation']}")
        #         print(f"ASCII коды: {parsed['ascii_codes']}")
                
        #         print("\nБИТОВЫЙ АНАЛИЗ:")
        #         for key, value in parsed["bit_analysis"].items():
        #             print(f"  {key}: {value}")
                
        #         print("\nРАСШИФРОВКА ФЛАГОВ:")
        #         for char, meaning in parsed["decoded_flags"].items():
        #             print(f"  '{char}': {meaning}")
                
        #         if "combined_binary" in parsed:
        #             print(f"\nКомбинированная битовая маска: {parsed['combined_binary']}")
        #             print("СТАНДАРТНЫЕ ФЛАГИ:")
        #             for flag, value in parsed["standard_flags"].items():
        #                 status = "ВКЛ" if value == "1" else "ВЫКЛ"
        #                 print(f"  {flag}: {status}")
        #     else:
        #         print("Ошибка парсинга QFLAG")

        # else:
        #     print("Нет такой команды")


if __name__ == "__main__":
    main()


    