cmake_minimum_required(VERSION 3.16)

project(recovery_witness LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(ecu_bench src/ecu_bench.cpp)

if (MSVC)
    target_compile_options(ecu_bench PRIVATE /W4 /WX)
else()
    target_compile_options(ecu_bench PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

enable_testing()
add_test(NAME ecu_bench_help COMMAND ecu_bench --help)
