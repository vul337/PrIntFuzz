#ifndef INCLUDE_PCI_ID_H_
#define INCLUDE_PCI_ID_H_

#include <functional>
#include <string>
#include "llvm/IR/Constant.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/Module.h"

#include "analyzer/analyzer.h"

enum DriverType {
	kPCIDriver,
	kUSBDriver,
	kI2CDriver,
};

class PCIIDAnalyzer: public Analyzer {
public:
    PCIIDAnalyzer(const std::string &, const std::string &);

    void process(json::iterator, std::reference_wrapper<json>) override;
};

class PCIID: public Processor {
public:
    PCIID(llvm::Module *, json &);

    bool processBC();
private:
    llvm::Module * llvm_bc_file_;
    json &output_json_;

    bool processTable(llvm::GlobalVariable *, json &, int);
	bool findDeviceID(DriverType);
	llvm::ConstantStruct *findDriver(DriverType, int &);
    template<typename ... Args>
    std::string string_format( const std::string& format, Args ... args );
};

#endif
