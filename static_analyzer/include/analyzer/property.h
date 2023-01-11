#ifndef INCLUDE_PROPERTY_H_
#define INCLUDE_PROPERTY_H_

#include <functional>
#include <set>

#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/InstVisitor.h"

#include "analyzer/analyzer.h"

typedef std::tuple<std::string, uint8_t, uint64_t> ReadFunc;

class PropertyAnalyzer: public Analyzer {
public:
    PropertyAnalyzer(const std::string &, const std::string &);

    void process(json::iterator, std::reference_wrapper<json>) override;
};

class Property: public Processor, public llvm::InstVisitor<Property> {
public:
    Property(llvm::Module *, json &);

    bool processBC();

    void visitCallInst(llvm::CallInst &);
private:
    llvm::Module *llvm_bc_file_;
    json &output_json_;

    llvm::Function *probe_func_;
    bool has_interrupt_handler_;
    bool is_pci_bus_;
    bool is_usb_bus_;
    bool is_i2c_bus_;
    bool has_probe_func_;
    bool has_driver_name_;
	uint8_t reg_width_;
	int alternate_setting_number_;
    std::vector<std::string> error_site_;
    std::set<llvm::Function *> visited_function_;
	std::set<std::pair<llvm::BasicBlock *, int>> visited_bb_;
	std::set<llvm::BasicBlock *> bb_vector_;
    std::set<llvm::PHINode *> visited_phi_;
    std::set<llvm::Function *> CalledFunctionSet;
	std::map<std::pair<uint8_t, uint8_t>, std::vector<uint64_t>> pci_config_;
	std::vector<int> pci_resource_;
	std::vector<std::pair<uint8_t, uint64_t>> reg_value_;
	const std::vector<ReadFunc> default_read_funcs_ = {
		std::make_tuple("readb", 2, 0xff),
		std::make_tuple("readw", 4, 0xffff),
		std::make_tuple("readl", 8, 0xffffffff),
		std::make_tuple("inb", 2, 0xff),
		std::make_tuple("inw", 4, 0xffff),
		std::make_tuple("inl", 8, 0xffffffff),
		std::make_tuple("ioread8", 2, 0xff),
		std::make_tuple("ioread16", 4, 0xffff),
		std::make_tuple("ioread16be", 4, 0xffff),
		std::make_tuple("ioread32", 8, 0xffffffff),
		std::make_tuple("ioread32be", 8, 0xffffffff),

		std::make_tuple("regmap_read", 0, 0),
		std::make_tuple("i2c_smbus_read_byte", 2, 0xff),
		std::make_tuple("i2c_smbus_read_byte_data", 2, 0xff),
		std::make_tuple("i2c_smbus_read_word_data", 4, 0xffff),
		std::make_tuple("i2c_smbus_read_word_swapped", 4, 0xffff),
		std::make_tuple("i2c_smbus_read_block_data", 8, 0xffffffff),
		std::make_tuple("i2c_smbus_read_i2c_block_data", 8, 0xffffffff),
	};
	std::vector<ReadFunc> read_funcs_;
	int pci_dev_func_;

	uint64_t widthToMask(uint8_t);
    bool findIntPCI();
    bool findProbeFunc();
	void findAlternateSetting(llvm::Function *);
    bool findErrorSite(llvm::Function *, std::set<llvm::CallInst *> &);
    bool findDriverName();
    bool findBug(llvm::Function *);
	bool findRegWidth(llvm::Function *);
	void findPCIConfig(llvm::Function *);
	void findPCIResource(llvm::Function *);
	void findReg(llvm::Function *);
	void findReadFunc();
	ReadFunc isReadFunc(llvm::Function *);
	llvm::BinaryOperator *isAndInst(llvm::Value *);
	uint64_t findRegCheck(llvm::Value *, const std::string& width);
	uint64_t findRegCheck(llvm::Value *);
	uint64_t findEquality(llvm::Value *);
    void findDMA(llvm::Function *);
    bool handleReturnValue(llvm::Value *, llvm::Function *);
	bool isError(llvm::ICmpInst *, int successor_pos);
    llvm::ConstantStruct *findDriver();
	llvm::Value * findUser(llvm::Value *);
};

#endif
