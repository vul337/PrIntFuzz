#include "analyzer/pci_id.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/GlobalValue.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/Support/Casting.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/IRReader/IRReader.h"
#include <functional>
#include <mutex>
#include <type_traits>
#include <sstream>

PCIIDAnalyzer::PCIIDAnalyzer(const std::string &intput_json, const std::string &output_json)
    :Analyzer(intput_json, output_json) {}

void PCIIDAnalyzer::process(json::iterator it, std::reference_wrapper<json> output_json) {
    json &tmp_output_json = output_json;
	llvm::StringRef llvm_bc = it.key();
    llvm::LLVMContext llvm_context;
	llvm::SMDiagnostic llvm_error;

    if (!it->contains("Device Bus") || (tmp_output_json["Device Bus"] != "PCI" 
        && tmp_output_json["Device Bus"] != "USB" && tmp_output_json["Device Bus"] != "I2C"))
        return;

	auto llvm_bc_file = llvm::parseIRFile(llvm_bc, llvm_error, llvm_context).release();
	if (!llvm_bc_file) {
		ErrorLog("The bitcode " << llvm_bc << " does not exist!");
		return;
	}
    NormalLog("[*]PCI ID: Processing bitcode: " << llvm_bc);
    auto processor_ = std::make_unique<PCIID>(llvm_bc_file, output_json);
    processor_->processBC();
}

PCIID::PCIID(llvm::Module *llvm_bc_file, json &output_json)
    :llvm_bc_file_(llvm_bc_file), output_json_(output_json) {}

bool PCIID::processBC() {
	findDeviceID(kPCIDriver);
	findDeviceID(kUSBDriver);
	findDeviceID(kI2CDriver);

    return true;
}

bool PCIID::findDeviceID(DriverType driver_type) {
	int id_table_pos = -1;
	llvm::ConstantStruct *driver_struct = findDriver(driver_type, id_table_pos);
	if (!driver_struct) {
		return false;
	}

	llvm::Constant *get_device_id = NULL;	
	if (driver_type == kPCIDriver) {
		get_device_id = driver_struct->getAggregateElement(2);
	} else if (driver_type == kUSBDriver) {
		get_device_id = driver_struct->getAggregateElement(id_table_pos);
	} else if (driver_type == kI2CDriver) {
		get_device_id = driver_struct->getAggregateElement(8);
	}
	if (!get_device_id) {
		return false;
	}

	auto *device_id = llvm::dyn_cast<llvm::GlobalVariable>(get_device_id->getOperand(0));
	if (!device_id) {
		return false;
	}

	if (driver_type == kPCIDriver) {
		processTable(device_id, output_json_["PCI Device ID"], driver_type);
	} else if (driver_type == kUSBDriver) {
		processTable(device_id, output_json_["USB Device ID"], driver_type);
	} else if (driver_type == kI2CDriver) {
		processTable(device_id, output_json_["I2C Device ID"], driver_type);
	}

	return true;
}

llvm::ConstantStruct *PCIID::findDriver(DriverType driver_type, int &id_table_pos) {
	llvm::ConstantStruct *driver_struct = NULL;
	auto &global_list = llvm_bc_file_->getGlobalList();
	for (auto &global : global_list) {
        auto *actualType = GV2Type(&global, 0);
		if (!actualType) {
			continue;
		}
		if (driver_type == kUSBDriver) {
			if (actualType->getStructName().str().find("struct.usb_serial_driver") 
					!= std::string::npos) {
				id_table_pos = 1;
			} else if (actualType->getStructName().str().find("struct.usb_driver") 
					!= std::string::npos) {
				id_table_pos = 9;
			} else {
				continue;
			}
		} else {
			std::string struct_name;
			if (driver_type == kPCIDriver) {
				struct_name = "struct.pci_driver";
			} else if (driver_type == kI2CDriver) {
				struct_name = "struct.i2c_driver";
			}
			if (!actualType || actualType->getStructName().str().find(struct_name) == std::string::npos)
				continue;
		}
        auto *actual_constant = GV2Constant(&global, 0);
        if (!actual_constant) {
            continue;
        }
        driver_struct = llvm::dyn_cast<llvm::ConstantStruct>(actual_constant);
        if (driver_struct) {
            return driver_struct;
        }
	}

	return driver_struct;
}

bool PCIID::processTable(llvm::GlobalVariable *global_variable, json &pci_device_id, int type) {
    bool flag = false;
    std::string base_name;

    if (type == 1) {
        base_name = "usb_device_id";
    } else if (type == 2) {
        base_name = "i2c_device_id";
    } else {
        base_name = "pci_device_id";
    }

    auto *actual_constant = GV2Constant(global_variable, 1);
    if (!actual_constant) {
        return flag;
    }
    for (unsigned i = 0; i < actual_constant->getNumOperands(); i++) {
        llvm::Constant *arrayItem = actual_constant->getAggregateElement(i);
        if (!arrayItem) {
            continue;
        }
        std::string item_name = base_name + string_format("%03d", i+1);
        if (type == 2) {
            auto *data_array = llvm::dyn_cast<llvm::ConstantDataArray>(
                    arrayItem->getAggregateElement((unsigned)0));
            std::string driver_name_str;
            if (data_array) {
                if (data_array->isCString()) {
                    driver_name_str = data_array->getAsCString().str();
                } else {
                    driver_name_str = data_array->getAsString().str().c_str();
                }
                pci_device_id[item_name].push_back(driver_name_str);
                continue;
            }
        }
        for (unsigned j = 0; j < arrayItem->getNumOperands(); j++) {
            llvm::ConstantInt *arrayConstant = 
                llvm::dyn_cast<llvm::ConstantInt>(arrayItem->getAggregateElement(j));
            if (arrayConstant == nullptr) {
                continue;
            }
            std::lock_guard<std::mutex> mutex(mutex_);
            std::stringstream ss;
			if (type == 0) {
				ss << std::hex << (int32_t)arrayConstant->getZExtValue();
			} else {
				ss << std::hex << (int16_t)arrayConstant->getZExtValue();
			}
            pci_device_id[item_name].push_back("0x" + std::string{ss.str()});
        }
    }
    return flag;
}

template<typename ... Args>
std::string PCIID::string_format( const std::string& format, Args ... args )
{
    int size_s = std::snprintf( nullptr, 0, format.c_str(), args ... ) + 1; // Extra space for '\0'
    if( size_s <= 0 ){ throw std::runtime_error( "Error during formatting." ); }
    auto size = static_cast<size_t>( size_s );
    auto buf = std::make_unique<char[]>( size );
    std::snprintf( buf.get(), size, format.c_str(), args ... );
    return std::string( buf.get(), buf.get() + size - 1 ); // We don't want the '\0' inside
}
