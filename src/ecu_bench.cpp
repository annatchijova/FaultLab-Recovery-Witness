#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cctype>

namespace {

struct Event {
    int sequence;
    const char* event_type;
};

struct Scenario {
    std::string fault;
    std::string outcome;
    std::vector<Event> events;
};

void print_usage() {
    std::cout << "Usage: ecu_bench --fault <power_drop|message_loss|recovery_incomplete> "
                 "--case-id <id> --run-id <id> --oracle-file <path> [--interactive]\n";
}

void validate_identifier(const std::string& value, const char* name) {
    if (value.empty() || value.size() > 128) {
        throw std::invalid_argument(std::string(name) + " must contain 1..128 characters");
    }
    for (unsigned char character : value) {
        if (!std::isalnum(character) && character != '-' && character != '_' &&
            character != '.') {
            throw std::invalid_argument(
                std::string(name) + " contains an unsupported character");
        }
    }
}

Scenario scenario_for(const std::string& fault) {
    if (fault == "power_drop") {
        return {fault, "module_restarted", {
            {1, "diagnostic_request"},
            {2, "response_timeout"},
            {3, "module_restart"},
            {4, "module_initialized"},
        }};
    }
    if (fault == "message_loss") {
        return {fault, "transport_timeout_without_restart", {
            {1, "diagnostic_request"},
            {2, "response_timeout"},
            {3, "transport_recovered"},
        }};
    }
    if (fault == "recovery_incomplete") {
        return {fault, "module_not_ready_after_recovery", {
            {1, "diagnostic_request"},
            {2, "persistence_interrupted"},
            {3, "recovery_started"},
            {4, "module_not_ready"},
        }};
    }
    throw std::invalid_argument("unknown fault scenario: " + fault);
}

void write_oracle(const std::filesystem::path& path, const Scenario& scenario) {
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("cannot open oracle file: " + path.string());
    }
    output << "{\"schema_version\":\"oracle.v1\",\"fault\":\""
           << scenario.fault << "\",\"outcome\":\"" << scenario.outcome
           << "\"}\n";
}

void await_request() {
    std::string command;
    if (!std::getline(std::cin, command) || command != "NEXT") {
        throw std::runtime_error("expected NEXT request");
    }
}

void write_public_events(
    const Scenario& scenario,
    const std::string& case_id,
    const std::string& run_id, bool interactive) {
    for (const Event& event : scenario.events) {
        if (interactive) await_request();
        std::cout << "{\"schema_version\":\"event.v1\","
                     "\"case_id\":\"" << case_id << "\","
                     "\"run_id\":\"" << run_id << "\","
                     "\"sequence\":" << event.sequence << ","
                     "\"source\":\"bench\","
                     "\"clock_domain\":\"simulated\","
                     "\"event_type\":\"" << event.event_type << "\","
                     "\"observed\":true}\n";
        if (interactive) std::cout.flush();
    }
    if (interactive) {
        await_request();
        std::cout << "END" << std::endl;
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            print_usage();
            return 0;
        }
        const bool interactive = argc == 10 && std::string(argv[9]) == "--interactive";
        if ((argc != 9 && !interactive) || std::string(argv[1]) != "--fault" ||
            std::string(argv[3]) != "--case-id" ||
            std::string(argv[5]) != "--run-id" ||
            std::string(argv[7]) != "--oracle-file") {
            print_usage();
            return 2;
        }

        const Scenario scenario = scenario_for(argv[2]);
        validate_identifier(argv[4], "case-id");
        validate_identifier(argv[6], "run-id");
        write_oracle(argv[8], scenario);
        write_public_events(scenario, argv[4], argv[6], interactive);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ecu_bench: " << error.what() << '\n';
        return 1;
    }
}
