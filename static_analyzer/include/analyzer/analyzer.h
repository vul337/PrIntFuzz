#ifndef INCLUDE_ANALYZER_H_
#define INCLUDE_ANALYZER_H_

#include <functional>
#include <memory>
#include <iostream>
#include <string>

#include "third_party/json.hpp"
#include "third_party/threadpool.h"
#include "support/json_read_write.h"
#include "support/debuger.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/Constants.h"

using json = nlohmann::json;

class Processor {
public:
    virtual bool processBC() = 0;

protected:
    llvm::Type* GV2Type(llvm::GlobalVariable *, int );
    llvm::Constant* GV2Constant(llvm::GlobalVariable *, int );
    std::mutex mutex_;
};

class Analyzer {
public:
    Analyzer(const std::string &input_json, const std::string &output_json)
        :input_json_(input_json), output_json_(output_json) {}

    void processGenerally() {
        ThreadPool pool(std::thread::hardware_concurrency());

        std::unique_ptr<JsonReadWrite> input_json = std::make_unique<JsonReadWrite>(input_json_, kFileRead);
        std::unique_ptr<JsonReadWrite> output_json = std::make_unique<JsonReadWrite>(output_json_, kFileWrite);

        output_json->json_file_ = json::parse(input_json->json_file_.dump());
        for (json::iterator it = input_json->json_file_.begin();
            it != input_json->json_file_.end(); ++it) {
            const std::string &llvm_bc_name = it.key();
            pool.enqueue(&Analyzer::process, this, it, std::ref(output_json->json_file_[llvm_bc_name]));
        }
        pool.join();
    }

    virtual void process(json::iterator, std::reference_wrapper<json>) {};
protected:
    const std::string input_json_;
    const std::string output_json_;
};

#endif
