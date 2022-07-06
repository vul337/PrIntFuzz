#ifndef INCLUDE_DEBUGER_H_
#define INCLUDE_DEBUGER_H_

#include "llvm/Support/Debug.h"

#define Log(log) (llvm::dbgs() << log << "\n")

#define NormalLog(log) Log(log)
#define ErrorLog(log) Log(log)

#ifndef NDEBUG
    #define PrintLog(log) Log(log)
#else
    #define PrintLog(log)
#endif

#endif
