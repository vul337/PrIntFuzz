#include <memory>
#include <filesystem>

#include "analyzer/analyzer.h"
#include "analyzer/property.h"
#include "analyzer/pci_id.h"
#include "llvm/IR/CallingConv.h"

using json = nlohmann::json;

namespace fs = std::filesystem;

int main(int argc, char *argv[]) {
    std::unique_ptr<Analyzer> analyzer;

    const fs::path llvm_bc_json{argv[1]};
    const fs::path out_dir = llvm_bc_json.parent_path();
    const fs::path property_json = out_dir / "property.json";
    const fs::path pci_id_json = out_dir / "pci_id.json";
    const fs::path final_json = out_dir / "final.json";

    analyzer = std::make_unique<PropertyAnalyzer>(llvm_bc_json, property_json);
    analyzer->processGenerally();

    analyzer = std::make_unique<PCIIDAnalyzer>(property_json, pci_id_json);
    analyzer->processGenerally();

    std::unique_ptr<JsonReadWrite> input_json = std::make_unique<JsonReadWrite>(pci_id_json, kFileRead);
    std::unique_ptr<JsonReadWrite> output_json = std::make_unique<JsonReadWrite>(final_json, kFileWrite);

    output_json->json_file_ = json::parse(input_json->json_file_.dump());
    for (json::iterator it = input_json->json_file_.begin(); it != input_json->json_file_.end(); ++it) {
        if (it->size())
            continue;
        output_json->json_file_.erase(it.key());
    }
    
    return 0;
}
