#include "analyzer/analyzer.h"
#include "support/debuger.h"
#include "llvm/IR/Constant.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/Support/Casting.h"
#include "llvm/IR/Constants.h"
#include "llvm/Support/Debug.h"

llvm::Type* Processor::GV2Type(llvm::GlobalVariable *global_variable, int target_type) {
    llvm::Type *actual_type = NULL;
    llvm::Type *targetType = global_variable->getType();
    assert(targetType->isPointerTy()); //All global variable should be pointer
    llvm::Type *containedType = targetType->getContainedType(0); //Get true type of global variable

    if (target_type == 0) {
        auto *struct_type = llvm::dyn_cast<llvm::StructType>(containedType);
        if (struct_type && !struct_type->isLiteral()) {
            return struct_type;
        }
    } else if (target_type == 1) {
        auto *array_type = llvm::dyn_cast<llvm::ArrayType>(containedType);
        if (array_type) {
            return array_type;
        }
    }

    auto *targetSt = llvm::dyn_cast<llvm::StructType>(containedType);
    if (!targetSt) {
        return actual_type;
    }
    for (auto &element : targetSt->elements()) {
        if (0 == target_type) {
            auto *struct_type = llvm::dyn_cast<llvm::StructType>(element);
            if (!struct_type || struct_type->isLiteral())
                continue;
            actual_type = struct_type;
            break;
        } else if (1 == target_type) {
            auto *array_type = llvm::dyn_cast<llvm::ArrayType>(element);
            if (!array_type)
                continue;
            actual_type = array_type;
            break;
        }
    }

    return actual_type;
}

llvm::Constant* Processor::GV2Constant(llvm::GlobalVariable *global_variable, int target_type) {
    llvm::Constant *actual_constant = NULL;

    if (!global_variable->hasInitializer())
        return actual_constant;

    llvm::Constant *targetConstant = global_variable->getInitializer();

    if (target_type == 0) {
        actual_constant = llvm::dyn_cast<llvm::ConstantStruct>(targetConstant);
        if (actual_constant) {
            return actual_constant;
        }
    } else if (target_type == 1) {
        actual_constant = llvm::dyn_cast<llvm::ConstantArray>(targetConstant);
        if (actual_constant) {
            return actual_constant;
        }
    }

    actual_constant = llvm::dyn_cast<llvm::ConstantStruct>(targetConstant);
    if (!actual_constant)
        return actual_constant;
    unsigned int numOperands = actual_constant->getNumOperands();
    if (numOperands == 2) {
        if (target_type == 0) {
            actual_constant = llvm::dyn_cast<llvm::ConstantStruct>(actual_constant->getOperand(0));
        } else if (target_type == 1) {
            actual_constant = llvm::dyn_cast<llvm::ConstantArray>(actual_constant->getOperand(0));
        }
        if (!actual_constant)
            return actual_constant;
    }

    return actual_constant;
}
