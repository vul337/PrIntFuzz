add_library(Analyzer SHARED
    property.cpp
    pci_id.cpp
    analyzer.cpp)

target_link_libraries(Analyzer INTERFACE ${llvm_libs})

install(TARGETS Analyzer)
