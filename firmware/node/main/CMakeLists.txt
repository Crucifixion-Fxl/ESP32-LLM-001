idf_component_register(SRCS "ternary_lut.cpp" "bitlinear_forward_q.S" "bitlinear_forward.S" "qwen_attention.cpp" "bitlinear.cpp" "spi_bus.cpp" "app_main.cpp"
                       PRIV_REQUIRES spi_flash esp_psram esp_partition esp_timer esp_common esp_driver_spi esp_driver_gpio
                       INCLUDE_DIRS "")
