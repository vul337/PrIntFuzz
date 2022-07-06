cmake_minimum_required(VERSION 3.14)

project(static_analysis)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if (INTERRUPT_ANALYSIS)
	add_compile_options(-DINTERRUPT_ANALYSIS)
endif()

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  message("Setting build type to 'RelWithDebInfo' as none was specified.")
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Choose the type of build." FORCE)
endif()

find_package(LLVM 14 REQUIRED CONFIG PATHS ${LLVM_DIR})
add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS} ${PROJECT_SOURCE_DIR}/include)
link_directories(${LLVM_LIBRARY_DIRS})
llvm_map_components_to_libnames(llvm_libs support core irreader)

# link_libraries(${llvm_libs})

add_subdirectory(src)
