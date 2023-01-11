#include "analyzer/property.h"
#include "support/debuger.h"
#include "llvm/IR/Constant.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/Instructions.h"
#include "llvm/Support/Casting.h"
#include "llvm/Support/Debug.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/IR/Operator.h"
#include "llvm/IR/InstIterator.h"
#include "llvm/ADT/Optional.h"
#include "llvm/ADT/STLForwardCompat.h"
#include "llvm/ADT/STLFunctionalExtras.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/IRReader/IRReader.h"
#include <memory>
#include <functional>
#include <mutex>
#include <sstream>

PropertyAnalyzer::PropertyAnalyzer(const std::string &input_json, const std::string &output_json)
    :Analyzer(input_json, output_json) {}

void PropertyAnalyzer::process(json::iterator it, std::reference_wrapper<json> output_json) {
	llvm::StringRef llvm_bc = it.key();
    llvm::LLVMContext llvm_context;
	llvm::SMDiagnostic llvm_error;

	auto llvm_bc_file = llvm::parseIRFile(llvm_bc, llvm_error, llvm_context).release();
	if (!llvm_bc_file) {
		ErrorLog("The bitcode " << llvm_bc << " does not exist!");
		return;
	}
    NormalLog("[*]Property: Processing bitcode " << llvm_bc);
    auto processor_ = std::make_unique<Property>(llvm_bc_file, output_json);
    processor_->processBC();
}

Property::Property(llvm::Module *llvm_bc_file, json &output_json)
    :llvm_bc_file_(llvm_bc_file), output_json_(output_json) {
    is_pci_bus_ = false;
    is_usb_bus_ = false;
    has_interrupt_handler_ = false;
    has_probe_func_ = false;
    has_driver_name_ = false;
	reg_width_ = 0xff;
	alternate_setting_number_ = -1;
	pci_dev_func_ = 0;

    visited_function_.clear();
    visited_phi_.clear();
	reg_value_.clear();
	pci_config_.clear();
	pci_resource_.clear();
	reg_value_.clear();
	read_funcs_.clear();

	visited_bb_.clear();
}

bool Property::processBC() {
    if (!findIntPCI())
        return true;

	findDriverName();
	findReadFunc();

    if(findProbeFunc()) {
		PrintLog("Found probe function " << probe_func_->getName().str());
		visited_function_.clear();
		if (is_usb_bus_) {
			findAlternateSetting(probe_func_);
		} else if (is_pci_bus_) {
			visited_function_.clear();
			findPCIConfig(probe_func_);

			visited_function_.clear();
			findPCIResource(probe_func_);

			visited_function_.clear();
			findReg(probe_func_);

			visited_function_.clear();
			visited_phi_.clear();
			findBug(probe_func_);

			visited_function_.clear();
			visited_phi_.clear();
			findDMA(probe_func_);
		} else if (is_i2c_bus_) {
			visited_function_.clear();
			findRegWidth(probe_func_);

			visited_function_.clear();
			reg_value_.clear();
			findReg(probe_func_);
		}
	}

    mutex_.lock();
	output_json_["Driver Info"] = {};
	output_json_["Driver Info"]["Read Funcs"] = read_funcs_;
	if (is_pci_bus_) {
		output_json_["Driver Info"]["PCI"] = {};
		output_json_["Driver Info"]["PCI"]["PCI Config"] = pci_config_;
		output_json_["Driver Info"]["PCI"]["PCI Resource"] = pci_resource_;
		output_json_["Driver Info"]["PCI"]["PCI Reg"] = reg_value_;
		output_json_["Driver Info"]["PCI"]["PCI Func"] = pci_dev_func_;
	} else if (is_usb_bus_) {
		output_json_["Driver Info"]["USB"] = {};
		output_json_["Driver Info"]["USB"]["AlternateSetting"] = alternate_setting_number_;
	} else if (is_i2c_bus_) {
		output_json_["Driver Info"]["I2C"] = {};
		output_json_["Driver Info"]["I2C"]["Reg Value"] = reg_value_;
		output_json_["Driver Info"]["I2C"]["Reg Width"] = reg_width_;
	}
    mutex_.unlock();

    return true;
}

void Property::findReadFunc() {
	auto &funcs = llvm_bc_file_->getFunctionList();
	for (auto &func: funcs) {
		if (!func.hasName()) {
			continue;
		}
		const auto read_func = isReadFunc(&func);
		if (std::get<1>(read_func)) {
			read_funcs_.emplace_back(read_func);
		} else {
			for (auto &read_func: default_read_funcs_) {
				auto func_name = func.getName().str();
				if (func_name.compare(std::get<0>(read_func))) {
					continue;
				}
				read_funcs_.emplace_back(read_func);
			}
		}
	}
	return;
}

ReadFunc Property::isReadFunc(llvm::Function *func) {
	ReadFunc read_func{func->getName().str(), 0, 0};
	const auto &func_name = func->getName().str();

	if (func_name.find("read") == std::string::npos || 
			func->getBasicBlockList().size() > 5) {
		return read_func;
	}

	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
		if (!call_inst) {
			continue;
		}
		auto *called_function = call_inst->getCalledFunction();
		if (!called_function || !called_function->hasName()) {
			continue;
		}
		const auto &called_function_name = called_function->getName().str();
		for (auto &tmp_read_func: default_read_funcs_) {
			if (called_function_name.compare(std::get<0>(tmp_read_func))) {
				continue;
			}
			std::get<1>(read_func) = std::get<1>(tmp_read_func);
			std::get<2>(read_func) = std::get<2>(tmp_read_func);
		}
	}

	return read_func;
}

void Property::findReg(llvm::Function *func) {
    if (visited_function_.find(func) != visited_function_.end()) {
        return;
    }
    visited_function_.insert(func);

	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
		if (!call_inst) {
			continue;
		}
		auto *called_function = call_inst->getCalledFunction();
		if (!called_function || !called_function->hasName()) {
			continue;
		}
		if (!called_function->isDeclaration()) {
			findReg(called_function);
		}
		const auto &called_function_name = called_function->getName().str();
		for (auto &read_func: read_funcs_) {
			const auto &read_func_name = std::get<0>(read_func);
			if (called_function_name.find(read_func_name) == std::string::npos) {
				continue;
			}
			uint64_t reg_value = 0xffffffff;
			if (!called_function_name.compare("regmap_read")) {
				reg_value = findRegCheck(call_inst->getArgOperand(2));
				reg_value_.emplace_back(std::make_pair(reg_width_, reg_value & widthToMask(reg_width_)));
			} else {
				for (auto *user: call_inst->users()) {
					auto *store_inst = llvm::dyn_cast<llvm::StoreInst>(user);
					if (!store_inst) {
						continue;
					}
					auto *value_operand = store_inst->getValueOperand();
					llvm::Value *to_check_value = NULL;
					if (value_operand == call_inst) {
						to_check_value = store_inst->getPointerOperand();
					} else {
						to_check_value = store_inst->getValueOperand();
					}
					reg_value = findRegCheck(to_check_value);
					break;
				}
				reg_value_.emplace_back(std::make_pair(std::get<1>(read_func), reg_value & std::get<2>(read_func)));
			}
		}
	}
}

uint64_t Property::widthToMask(uint8_t width) {
	uint64_t mask = 0;
	if (width == 2) {
		mask = 0xff;
	} else if (width == 4) {
		mask = 0xffff;
	} else if (width == 8) {
		mask = 0xffffffff;
	}

	return mask;
}

void Property::findPCIResource(llvm::Function *func) {
    if (visited_function_.find(func) != visited_function_.end()) {
        return;
    }
    visited_function_.insert(func);

	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto *alloc_inst = llvm::dyn_cast<llvm::AllocaInst>(&*I);
		if (!alloc_inst) {
			continue;
		}
		auto *allocated_type = alloc_inst->getAllocatedType();
		if (!allocated_type->isPointerTy()) {
			continue;
		}
		auto *struct_type = allocated_type->getContainedType(0);
		if (!struct_type->isStructTy()) {
			continue;
		}
		const auto &allocated_type_name = struct_type->getStructName().str();
		if (allocated_type_name.compare("struct.pci_dev")) {
			continue;
		}
		for (auto *user: alloc_inst->users()) {
			auto *load_inst = llvm::dyn_cast<llvm::LoadInst>(user);
			if (!load_inst) {
				continue;
			}
			for (auto *load_inst_user: load_inst->users()) {
				auto *getelementptr_inst = llvm::dyn_cast<llvm::GetElementPtrInst>(load_inst_user);
				if (!getelementptr_inst) {
					continue;
				}
				auto *constant_1 = llvm::dyn_cast<llvm::ConstantInt>(getelementptr_inst->getOperand(2));
				if (!constant_1) {
					continue;
				}
				if (constant_1->getZExtValue() == 51) {
					for (auto *gep_inst_user: getelementptr_inst->users()) {
						auto gep_inst = llvm::dyn_cast<llvm::GetElementPtrInst>(gep_inst_user);
						if (!gep_inst) {
							continue;
						}
						auto *target_type = gep_inst->getResultElementType();
						if (!target_type || !target_type->isStructTy() ||
								target_type->getStructName().str().compare("struct.resource")) {
							continue;
						}
						auto *constant_2 = llvm::dyn_cast<llvm::ConstantInt>(gep_inst->getOperand(2));
						if (!constant_2) {
							continue;
						}
						int tmp_bar = constant_2->getZExtValue();
						for (auto *gep_inst_user_2: gep_inst->users()) {
							auto gep_inst_2 = llvm::dyn_cast<llvm::GetElementPtrInst>(gep_inst_user_2);
							if (!gep_inst_2) {
								continue;
							}
							auto *constant_3 = llvm::dyn_cast<llvm::ConstantInt>(gep_inst_2->getOperand(2));
							if (!constant_3 || constant_3->getZExtValue() != 3) {
								continue;
							}
							for (auto gep_inst_user_3: gep_inst_2->users()) {
								auto *load_inst = llvm::dyn_cast<llvm::LoadInst>(gep_inst_user_3);
								if (!load_inst) {
									continue;
								}
								for (auto *load_inst_user: load_inst->users()) {
									auto *and_inst = llvm::dyn_cast<llvm::Instruction>(isAndInst(load_inst_user));
									if (!and_inst) {
										continue;
									}
									auto *mask = llvm::dyn_cast<llvm::ConstantInt>(and_inst->getOperand(1));
									if (!mask || mask->getZExtValue() != 0x100 ) {
										continue;
									}
									for (auto *and_inst_user: and_inst->users()) {
										auto *icmp_inst = llvm::dyn_cast<llvm::ICmpInst>(and_inst_user);
										auto predicate = icmp_inst->getPredicate();
										if ((predicate == llvm::ICmpInst::Predicate::ICMP_EQ && isError(icmp_inst, 0)) ||
												predicate == llvm::ICmpInst::Predicate::ICMP_NE && isError(icmp_inst, 1)) {
											pci_resource_.emplace_back(constant_2->getZExtValue());
											break;
										}
									}
								}
							}
						}
					} 
				} else if (constant_1->getZExtValue() == 6) {
					for (auto *gep_inst_user: getelementptr_inst->users()) {
						auto *load_inst = llvm::dyn_cast<llvm::LoadInst>(gep_inst_user);
						if (!load_inst) {
							continue;
						}
						for (auto *load_inst_user: load_inst->users()) {
							auto *and_inst = isAndInst(load_inst_user);
							if (!and_inst) {
								continue;
							}
							auto *mask = llvm::dyn_cast<llvm::ConstantInt>(and_inst->getOperand(1));
							if (!mask || mask->getZExtValue() != 7) {
								continue;
							}
							for (auto *and_inst_user: and_inst->users()) {
								auto *cmp_inst = 
									llvm::dyn_cast<llvm::ICmpInst>(and_inst_user);
								if (!cmp_inst || !cmp_inst->isEquality()) {
									continue;
								}
								auto *pci_dev_func = llvm::dyn_cast<llvm::ConstantInt>(cmp_inst->getOperand(1));
								if (!pci_dev_func) {
									continue;
								}
								pci_dev_func_ = pci_dev_func->getZExtValue();
								break;
							}
						}
					}
				}
			}
		}
	}

	return;
}

void Property::findPCIConfig(llvm::Function *func) {
    if (visited_function_.find(func) != visited_function_.end()) {
        return;
    }
    visited_function_.insert(func);

	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
		if (!call_inst) {
			continue;
		}
		auto *called_function = call_inst->getCalledFunction();
		if (!called_function || !called_function->hasName()) {
			continue;
		}
		if (!called_function->isDeclaration()) {
			findPCIConfig(called_function);
		}
		const auto &called_function_name = called_function->getName().str();
		int reg_width = 0;
		uint64_t mask = 0;
		if (!called_function_name.compare("pci_read_config_word")) {
			reg_width = 2;
			mask = 0xffff;
		} else if (!called_function_name.compare("pci_read_config_byte")) {
			reg_width = 1;
			mask = 0xff;
		} else if (!called_function_name.compare("pci_read_config_dword")) {
			reg_width = 4;
			mask = 0xffffffff;
		} else {
			continue;
		}
		auto* reg_pos_value = llvm::dyn_cast<llvm::ConstantInt>(
				call_inst->getArgOperand(1));
		if (reg_pos_value) {
			uint8_t reg_pos = reg_pos_value->getZExtValue();
			uint64_t reg_value = findRegCheck(call_inst->getArgOperand(2));
			pci_config_[std::make_pair(reg_pos, reg_width)].emplace_back(reg_value & mask);
			PrintLog("Find a value "<< (reg_value & mask) << " for " << *call_inst);
		} else {
			ErrorLog("The argument of 'pci_read_config_word/byte' is not a constant.");
			// TODO:Handle other cases
		}
	}
	return;
}

uint64_t Property::findRegCheck(llvm::Value *reg) {
	uint64_t ret = -1;

	for (auto *user: reg->users()) {
		auto load_inst = llvm::dyn_cast<llvm::LoadInst>(user);
		if (!load_inst) {
			continue;
		}
		/* 
		 * Second pattern: wm8962
		 * %0 = load i32, i32* %1
		 * %2 = icmp eq i32 %0, CONSTANT
		 */
		ret = findEquality(load_inst);
		if (ret != -1) {
			break;
		}
		for (auto *load_inst_user: load_inst->users()) {
			auto *user = findUser(load_inst_user);
			ret = findEquality(user);
			if (ret != -1) {
				break;
			}
		}
		if (ret != -1) {
			break;
		}
	}

	return ret;
}

llvm::Value *Property::findUser(llvm::Value *load_inst_user) {
	llvm::Value *user = load_inst_user;
	auto *and_inst = isAndInst(user);
	if (and_inst) {
		return and_inst;
	}
	/*
	 * Third pattern:
	 * %0 = load i32, i32* %1
	 * %2 = zext i16 %0 to i32
	 * %3 = and i32 %2, MASK
	 * %4 = icmp ne i32 %3, CMP_VALUE
	 */
	auto *cast_inst = llvm::dyn_cast<llvm::CastInst>(user);
	if (cast_inst) {
		for (auto *cast_inst_user: cast_inst->users()) {
			auto *and_inst = isAndInst(cast_inst_user);
			if (and_inst) {
				return and_inst;
			}
		}
	}
	/*
	 * First pattern:
	 * %0 = load i32, i32* %1
	 * %2 = and i32 %0, MASK
	 * %3 = icmp ne i32 %2, CMP_VALUE
	 */
	/*
	 *
	 * Fourth pattern:
	 * %0 = load i32, i32* %1
	 * %2 = zeit i16 %0 to i32
	 * %3 = icmp ne i32 %2, CMP_VALUE
	 */
	return user;
}

llvm::BinaryOperator* Property::isAndInst(llvm::Value *user) {
	llvm::BinaryOperator *and_inst = llvm::dyn_cast<llvm::BinaryOperator>(user);
	if (and_inst && !strcmp(and_inst->getOpcodeName(), "and")) {
		return and_inst;
	}
	return and_inst;
}

bool Property::findIntPCI() {
    has_interrupt_handler_ = is_pci_bus_ = is_usb_bus_ = is_i2c_bus_ = false;
    for (auto &function : *llvm_bc_file_) {
        if (!function.hasName()) {
            continue;
        }
        const std::string &function_name = function.getName().str();
#ifdef INTERRUPT_ANALYSIS
        if (function_name.find("request_threaded_irq") != function_name.npos) {
            has_interrupt_handler_ = true;
        }
#endif
        if (function_name.find("__pci_register_driver") != function_name.npos ||
            function_name.find("drm_legacy_pci_init") != function_name.npos) {
            is_pci_bus_ = true;
        }
        if (function_name.find("usb_register_driver") != function_name.npos ||
				function_name.find("usb_serial_register_drivers") != function_name.npos)
            is_usb_bus_ = true;
        if (function_name.find("i2c_register_driver") != function_name.npos) {
            is_i2c_bus_ = true;
        }
    }
    if (is_pci_bus_) {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Device Bus"] = "PCI";
    }
    
    if (is_usb_bus_) {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Device Bus"] = "USB";
    }

    if (is_i2c_bus_) {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Device Bus"] = "I2C";
    }

    if (has_interrupt_handler_) {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Interrupt"] = "Yes";
    }
    
    if (!output_json_["Source File"].size()) {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Source File"] = llvm_bc_file_->getSourceFileName();
    }

    return is_pci_bus_ || is_usb_bus_ || is_i2c_bus_;
}

llvm::ConstantStruct *Property::findDriver() {
    llvm::ConstantStruct *driver_struct = NULL;
    auto &global_list = llvm_bc_file_->getGlobalList();
	bool is_usb_serial = false;

    for (auto &global : global_list) {
        auto *actualType = GV2Type(&global, 0);
		if (!actualType) {
			continue;
		}
		const auto &struct_name = actualType->getStructName().str();
        if (is_pci_bus_ && struct_name.find("struct.pci_driver") == std::string::npos) {
            continue;
		}
        if (is_usb_bus_) {
			if (struct_name.find("struct.usb_serial_driver") != std::string::npos) {
				is_usb_serial = true;
			} else if (struct_name.find("struct.usb_driver") == std::string::npos) {
				continue;
			}
		}
        if (is_i2c_bus_ && struct_name.find("struct.i2c_driver") == std::string::npos) {
            continue;
		}
        auto *actual_constant = GV2Constant(&global, 0);
        if (!actual_constant) {
            continue;
        }
        driver_struct = llvm::dyn_cast<llvm::ConstantStruct>(actual_constant);
		if (is_usb_serial) {
			driver_struct = 
				llvm::dyn_cast<llvm::ConstantStruct>(driver_struct->getOperand(3));
		}
        if (driver_struct) {
            return driver_struct;
        }
    }

    return driver_struct;
}

bool Property::findDriverName() {
    auto *driver_struct = findDriver();
    if (!driver_struct)
        return has_driver_name_;
    llvm::Constant *driver_name = NULL;
    if (is_pci_bus_) {
        driver_name = driver_struct->getAggregateElement(1);
    } else if (is_usb_bus_) {
        driver_name = driver_struct->getAggregateElement((unsigned)0);
    } else if (is_i2c_bus_) {
        auto *driver_struct_2 = llvm::dyn_cast<llvm::ConstantStruct>(
                driver_struct->getAggregateElement(7));
        driver_name = driver_struct_2->getAggregateElement((unsigned)0);
    }
    if (!driver_name)
        return has_driver_name_;
    llvm::GEPOperator *gep = llvm::dyn_cast<llvm::GEPOperator>(driver_name);
    if (!gep) {
        return has_driver_name_;
    }
    llvm::GlobalVariable *struct_global = llvm::dyn_cast<llvm::GlobalVariable>(gep->getPointerOperand());
    if (!struct_global || !struct_global->hasInitializer()) {
        return has_driver_name_;
    }
    llvm::Constant *constant = struct_global->getInitializer();
    llvm::Constant *curr_constant = llvm::dyn_cast<llvm::Constant>(constant);
    if (!curr_constant) {
        return has_driver_name_;
    }
    unsigned int numOperands = curr_constant->getNumOperands();
    if (numOperands == 2) {
        curr_constant = llvm::dyn_cast<llvm::ConstantDataArray>(curr_constant->getOperand(0));
        if (!curr_constant)
            return has_driver_name_;
    }
    PrintLog("GetDeviceString: curr_constant: " << *curr_constant);
    llvm::ConstantDataArray *data_array = llvm::dyn_cast<llvm::ConstantDataArray>(curr_constant);
    std::string driver_name_str;
    if (data_array) {
        has_driver_name_ = true;
        if (data_array->isCString()) {
            driver_name_str = data_array->getAsCString().str();
        } else {
            driver_name_str = data_array->getAsString().str();
        }
        output_json_["Driver Name"] = driver_name_str;
    } else {
        //FIXME:When it is not a constant_data_arry;
        ErrorLog(*curr_constant);
    }    
    return has_driver_name_;
}

void Property::findAlternateSetting(llvm::Function *func) {
    if (visited_function_.find(func) != visited_function_.end()) {
        return;
    }
    visited_function_.insert(func);

	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
		if (!call_inst) {
			continue;
		}
		auto *called_function = call_inst->getCalledFunction();
		if (!called_function || !called_function->hasName()) {
			continue;
		}
		if (!called_function->isDeclaration()) {
			findAlternateSetting(called_function);
			if (alternate_setting_number_ != -1) {
				return;
			}
		}
		const auto &called_function_name = called_function->getName().str();
		if (!called_function_name.compare("usb_set_interface")) {
			auto *alternate_setting = call_inst->getArgOperand(2);
			assert(alternate_setting);
			auto alternate_setting_number = 
				llvm::dyn_cast<llvm::ConstantInt>(alternate_setting);
			if (alternate_setting_number) {
				alternate_setting_number_ = alternate_setting_number->getZExtValue();
			} else {
				auto *load_inst = llvm::dyn_cast<llvm::LoadInst>(alternate_setting);
				if (load_inst) {
					auto *source_operator = load_inst->getPointerOperand();
					for (auto *user: source_operator->users()) {
						auto store_inst = llvm::dyn_cast<llvm::StoreInst>(user);
						if (!store_inst) {
							continue;
						}
						auto *alternate_setting_number = 
							llvm::dyn_cast<llvm::ConstantInt>(store_inst->getValueOperand());
						if (alternate_setting_number && alternate_setting_number->getZExtValue() <= 6) {
							alternate_setting_number_ = alternate_setting_number->getZExtValue();
							return;
						}
					}
				}
			}
		}
	}
	return;
}

bool Property::findProbeFunc() {
	// TODO: Handle the case that usb serial driver
    auto *driver_struct = findDriver();
    if (!driver_struct)
        return has_probe_func_;
    llvm::Constant *driver_probe = NULL; 
    if (is_pci_bus_) {
        driver_probe = driver_struct->getAggregateElement(3);
    } else if (is_usb_bus_) {
        driver_probe = driver_struct->getAggregateElement(1);
    } else if (is_i2c_bus_) {
        driver_probe = driver_struct->getAggregateElement(3);
        probe_func_ = llvm::dyn_cast<llvm::Function>(driver_probe);
        if (!probe_func_) {
            driver_probe = driver_struct->getAggregateElement(1);
        }
    }
    probe_func_ = llvm::dyn_cast<llvm::Function>(driver_probe);
    if (!probe_func_ || !probe_func_->hasName())
        return has_probe_func_;
    {
        std::lock_guard<std::mutex> mutex(mutex_);
        output_json_["Probe Function"] = probe_func_->getName().str();
    }
    has_probe_func_ = true;

    if (!has_probe_func_)
        ErrorLog("This driver does not has probe function.");
    return has_probe_func_;
}

bool Property::findRegWidth(llvm::Function *func) {
	if (visited_function_.find(func) != visited_function_.end()) {
		return false;
	}
	visited_function_.insert(func);
	
	for (llvm::inst_iterator I = inst_begin(func), E = inst_end(func); I != E; ++I) {
		auto call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
		if (!call_inst) {
			continue;
		}
		auto called_function = call_inst->getCalledFunction();
		if (!called_function || !called_function->hasName()) {
			continue;
		}
		if (!called_function->isDeclaration()) {
			findRegWidth(called_function);
		}
		auto called_function_name = called_function->getName().str();
		int arg_pos = -1;
		if (!called_function_name.compare("__devm_regmap_init_i2c")) {
			arg_pos = 1;	
		} else if (!called_function_name.compare("__devm_regmap_init")) {
			arg_pos = 3;
		}
		if (arg_pos != -1) {
			auto regmap_config = llvm::dyn_cast<llvm::GlobalVariable>(
					call_inst->getOperand(arg_pos));
			if (!regmap_config || !regmap_config->hasInitializer()) {
				continue;
			}
			auto *init = regmap_config->getInitializer();
			reg_width_ = llvm::dyn_cast<llvm::ConstantInt>(
					init->getOperand(6))->getZExtValue() / 4;
		}
	}
	return reg_width_ != 0xff;
}

uint64_t Property::findRegCheck(llvm::Value *reg, const std::string& width) {
	uint64_t ret = -1;

	for (auto *user: reg->users()) {
		auto load_inst = llvm::dyn_cast<llvm::LoadInst>(user);
		if (!load_inst) {
			continue;
		}
		/* 
		 * Second pattern: wm8962
		 * %0 = load i32, i32* %1
		 * %2 = icmp eq i32 %0, CONSTANT
		 */
		ret = findEquality(load_inst);
		if (ret != -1) {
			break;
		}
		for (auto *load_inst_user: load_inst->users()) {
			/*
			 * First pattern:
			 * %0 = load i32, i32* %1
			 * %2 = and i32 %0, MASK
			 * %3 = icmp ne i32 %2, CMP_VALUE
			 */
			auto and_inst = llvm::dyn_cast<llvm::BinaryOperator>(load_inst_user);
			if (and_inst && !strcmp(and_inst->getOpcodeName(), "and")) {
				ret = findEquality(and_inst);
				if (ret != -1) {
					break;
				}
			}
		}
		if (ret != -1) {
			break;
		}
	}

	return ret;
}

uint64_t Property::findEquality(llvm::Value *inst) {
	uint64_t cmp_value = -1;

	for(auto *inst_user: inst->users()) {
		auto *icmp_inst = llvm::dyn_cast<llvm::ICmpInst>(inst_user);
		if (icmp_inst && icmp_inst->isEquality()) {
			auto *cmp_constant = llvm::dyn_cast<llvm::ConstantInt>(icmp_inst->getOperand(1));
			if (!cmp_constant) {
				cmp_constant = llvm::dyn_cast<llvm::ConstantInt>(icmp_inst->getOperand(0));
				if (!cmp_constant) {
					continue;
				}
			}
			auto predicate = icmp_inst->getPredicate();
			if ((predicate == llvm::ICmpInst::Predicate::ICMP_EQ && isError(icmp_inst, 1)) ||
					predicate == llvm::ICmpInst::Predicate::ICMP_NE && isError(icmp_inst, 0)) {
				cmp_value = cmp_constant->getZExtValue();
			}
			if (cmp_value != -1) {
				break;
			}
		}
		auto *switch_inst = llvm::dyn_cast<llvm::SwitchInst>(inst_user);
		if (switch_inst) {
			for (auto &switch_case: switch_inst->cases()) {
				cmp_value = switch_case.getCaseValue()->getZExtValue();
				if (cmp_value != -1) {
					break;
				}
			}
		}
		if (cmp_value != -1) {
			break;
		}
	}
	PrintLog("Find possible value " << cmp_value << " for inst: " << *inst);

	return cmp_value;
}

bool Property::isError(llvm::ICmpInst *inst, int successor_pos) {
	bool flag = false;

	if (!inst) {
		return flag;
	}

	PrintLog("Check if the inst " << *inst << " is an error cmp.");
	for (auto *user: inst->users()) {
		auto *branch_inst = llvm::dyn_cast<llvm::BranchInst>(user);
		if (!branch_inst) {
			continue;
		}
		auto *br_inst_2 = llvm::dyn_cast<llvm::BranchInst>(
				branch_inst->getSuccessor(successor_pos)->getTerminator());
		if (!br_inst_2) {
			continue;
		}
		auto *successor = br_inst_2->getParent()->getSingleSuccessor();
		if (!successor) {
			continue;
		}
		auto *ret_inst = llvm::dyn_cast<llvm::ReturnInst>(successor->getTerminator());
		int cnt = 0;
		while (!ret_inst && ++cnt <= 10) {
			auto *successor_2 = successor->getSingleSuccessor();
			if (!successor_2) {
				break;
			}
			ret_inst = llvm::dyn_cast<llvm::ReturnInst>(successor_2->getTerminator());
			successor = successor_2;
		}
		if (ret_inst) {
			flag = true;
			break;
		}
	}

	return flag;
}

bool Property::findBug(llvm::Function *function) {
    if (visited_function_.find(function) != visited_function_.end()) {
        return true;
    }
    visited_function_.insert(function);
    auto function_name = function->getName().str();
    if (function_name.find("foo") != function_name.npos) {
        for (llvm::inst_iterator I = inst_begin(function), E = inst_end(function); I != E; ++I) {
            auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&*I);
            if (!call_inst) {
                continue;
            }
            auto *called_function = call_inst->getCalledFunction();
            if (!called_function || !called_function->hasName()) {
                continue;
            }
            auto called_function_name = called_function->getName().str();
            if (called_function_name.find("error_prone") != called_function_name.npos ||
                    called_function_name.find("sanitizer") != called_function_name.npos) {
                continue;
            }
            if (call_inst) {
                findBug(call_inst->getCalledFunction());
            }
        }
    } else {
        for (llvm::inst_iterator I = inst_begin(function), E = inst_end(function); I != E; ++I) {
            llvm::ReturnInst* ret_inst = llvm::dyn_cast<llvm::ReturnInst>(&*I);
            if (ret_inst) {
                auto *return_value = ret_inst->getReturnValue();
                if (return_value) {
                    handleReturnValue(return_value, function);
                }
            }
        }
    }
    return true;
}

void Property::findDMA(llvm::Function * curr_function) {
    if (visited_function_.find(curr_function) != visited_function_.end()) {
        return;
    }
    visited_function_.insert(curr_function);
    for (auto &BB : *curr_function) {
        for (auto &I : BB) {
            auto *call_inst = llvm::dyn_cast<llvm::CallInst>(&I);
            if (call_inst) {
                auto called_function = call_inst->getCalledFunction();
                if (!called_function || !called_function->hasName()) {
                    continue;
                }
                if (!called_function->isDeclaration() && 
                        visited_function_.find(called_function) == visited_function_.end()) {
                    findDMA(called_function);
                }
                auto called_function_name = called_function->getName().str();
                if (called_function_name.find("dma_alloc_attrs") != called_function_name.npos) {
                    output_json_["DMA"] = "y";
                }
            }
        }
    }
}

bool Property::handleReturnValue(llvm::Value *return_value, llvm::Function *function) {
    // PrintLog("handleReturnValue: " << *return_value);
    auto *constant = llvm::dyn_cast<llvm::ConstantInt>(return_value);
    if (constant && !constant->isNegative() && !constant->isZero()) {
        NormalLog("!Find a bug in " << function->getName().str());
    }
    auto *phi = llvm::dyn_cast<llvm::PHINode>(return_value);
    if (phi && visited_phi_.find(phi) == visited_phi_.end()) {
        visited_phi_.insert(phi);
        for (auto &value: phi->incoming_values()) {
            handleReturnValue(value, function);
        }
    }
    auto *call_inst = llvm::dyn_cast<llvm::CallInst>(return_value);
    if (call_inst) {
        auto *called_function = call_inst->getCalledFunction();
        if (called_function && !called_function->isDeclaration() && 
                visited_function_.find(called_function) == visited_function_.end()) {
            findBug(called_function);
        }
    }
    return true;
}
