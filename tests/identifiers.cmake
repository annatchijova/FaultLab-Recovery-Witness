# Exercise both native argument positions with the same executable used by CTest.
string(RANDOM LENGTH 12 SUFFIX)
set(oracle "${CMAKE_CURRENT_BINARY_DIR}/identifier-test-${SUFFIX}.json")
function(check_identifiers case_id run_id expected_status)
    execute_process(COMMAND "${BENCH}" --fault message_loss --case-id "${case_id}"
        --run-id "${run_id}" --oracle-file "${oracle}"
        RESULT_VARIABLE status OUTPUT_VARIABLE events ERROR_VARIABLE error)
    if(NOT status EQUAL expected_status)
        message(FATAL_ERROR "Expected ${expected_status}, got ${status}: ${error}")
    endif()
    if(expected_status EQUAL 0)
        if(NOT EXISTS "${oracle}" OR NOT events MATCHES "diagnostic_request")
            message(FATAL_ERROR "Valid identifiers did not produce both artifacts")
        endif()
        file(REMOVE "${oracle}")
    elseif(EXISTS "${oracle}" OR NOT events STREQUAL "")
        message(FATAL_ERROR "Invalid identifiers produced evidence")
    endif()
endfunction()

string(REPEAT "a" 128 longest)
check_identifiers("${longest}" "A_z-1.0" 0)
check_identifiers("${longest}x" "valid" 1)
check_identifiers("valid" "invalid space" 1)
