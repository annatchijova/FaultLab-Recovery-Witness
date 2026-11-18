#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

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
                 "--oracle-file <path>\n";
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

void write_public_events(const Scenario& scenario) {
    for (const Event& event : scenario.events) {
        std::cout << "{\"schema_version\":\"event.v1\","
                     "\"case_id\":\"bench-case\","
                     "\"run_id\":\"bench-run\","
                     "\"sequence\":" << event.sequence << ","
                     "\"source\":\"bench\","
                     "\"clock_domain\":\"simulated\","
                     "\"event_type\":\"" << event.event_type << "\","
                     "\"observed\":true}\n";
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            print_usage();
            return 0;
        }
        if (argc != 5 || std::string(argv[1]) != "--fault" ||
            std::string(argv[3]) != "--oracle-file") {
            print_usage();
            return 2;
        }

        const Scenario scenario = scenario_for(argv[2]);
        write_oracle(argv[4], scenario);
        write_public_events(scenario);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ecu_bench: " << error.what() << '\n';
        return 1;
    }
}
