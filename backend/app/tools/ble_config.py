import json
from typing import Any, Dict
from .base import Tool, ToolResult

class BLEConfigTool(Tool):
    @property
    def name(self) -> str:
        return "ble_config"

    @property
    def description(self) -> str:
        return "Gera código de configuração BLE (C/C++) a partir de um JSON de serviços e características."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "config_json": {"type": "string", "description": "JSON com a estrutura de serviços e características"},
                "platform": {"type": "string", "description": "Plataforma alvo (ex: esp32, nrf52)", "default": "esp32"}
            },
            "required": ["config_json"]
        }

    def run(self, **kwargs) -> ToolResult:
        config_json = kwargs.get("config_json")
        platform = kwargs.get("platform", "esp32")
        if not config_json:
            return ToolResult(success=False, error="config_json é obrigatório")
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            return ToolResult(success=False, error=f"JSON inválido: {e}")

        if platform == "esp32":
            code = self._generate_esp32(config)
        else:
            code = self._generate_generic(config, platform)
        return ToolResult(success=True, data=code)

    def _generate_esp32(self, config: Dict) -> str:
        services = config.get("services", [])
        characteristics = config.get("characteristics", [])
        code = f"""// Código BLE gerado para ESP32 (ESP-IDF)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_bt.h"
#include "esp_gap_ble_api.h"
#include "esp_gatts_api.h"
#include "esp_bt_defs.h"
#include "esp_bt_main.h"
#include "esp_gatt_common_api.h"

#define GATTS_TAG "BLE_CONFIG"

// UUIDs dos serviços
"""
        for svc in services:
            name = svc.get('name', 'SERVICE')
            uuid = svc.get('uuid', '00000000-0000-0000-0000-000000000000')
            code += f"#define SERVICE_UUID_{name.upper()} {uuid}\n"

        code += """
// Características
"""
        for ch in characteristics:
            name = ch.get('name', 'CHAR')
            uuid = ch.get('uuid', '00000000-0000-0000-0000-000000000000')
            props = ch.get('properties', 'read')
            code += f"// {name}: {uuid} (props: {props})\n"

        code += """
// Estrutura para armazenar o perfil GATT
static uint8_t adv_config_done = 0;

// Callback de eventos GATT
static void gatts_profile_event_handler(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if, esp_ble_gatts_cb_param_t *param) {
    switch (event) {
        case ESP_GATTS_REG_EVT:
            ESP_LOGI(GATTS_TAG, "GATT registrado, if %d", gatts_if);
            break;
        case ESP_GATTS_READ_EVT:
            ESP_LOGI(GATTS_TAG, "Leitura GATT");
            break;
        case ESP_GATTS_WRITE_EVT:
            ESP_LOGI(GATTS_TAG, "Escrita GATT");
            break;
        default:
            break;
    }
}

void ble_config_init(void) {
    // Inicialização BLE (exemplo)
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    esp_bt_controller_init(&bt_cfg);
    esp_bt_controller_enable(ESP_BT_MODE_BTDM);
    esp_bluedroid_init();
    esp_bluedroid_enable();

    // Registrar perfil GATT (a implementar)
    ESP_LOGI(GATTS_TAG, "Inicialização BLE concluída");
}
"""
        return code

    def _generate_generic(self, config: Dict, platform: str) -> str:
        return f"// Código BLE para plataforma {platform} (genérico)\n" + json.dumps(config, indent=2)