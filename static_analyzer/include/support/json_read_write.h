#ifndef INCLUDE_JSON_READ_WRITE_H_
#define INCLUDE_JSON_READ_WRITE_H_

#include "third_party/json.hpp"
#include <fstream>

using json = nlohmann::json;

enum FileMode {
    kFileRead,
    kFileWrite,
    kFileRW
};

class JsonReadWrite {
public:
    json json_file_;
    
    JsonReadWrite(const std::string &file_name, FileMode mode)
        :file_mode_(mode) {
        if (kFileRead == file_mode_) {
            file_.open(file_name, std::ios::in);
            file_ >> json_file_;
        } else if (kFileWrite == file_mode_){
            file_.open(file_name, std::ios::out);
        } else {
            file_.open(file_name, std::ios::in | std::ios::out);
            file_ >> json_file_;
        }
    }

    ~JsonReadWrite() {
        if (kFileWrite == file_mode_ || kFileRW == file_mode_) {
            file_ << json_file_;
        }
        file_.close();
    }

private:
    std::fstream file_;
    FileMode file_mode_;
};

#endif
