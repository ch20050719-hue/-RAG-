#pragma once
#ifndef MCP_SERVER_H
#define MCP_SERVER_H
#include <functional>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
using ReturnValue = std::variant<bool, int, std::string>;
enum PropertyType { kPropertyTypeBoolean, kPropertyTypeInteger, kPropertyTypeString };
class Property {
    std::string name_;

public:
    Property(std::string name, PropertyType) : name_(name) {}
    template <class T>
    T value() const {
        throw std::runtime_error("No test argument supplied");
    }
    const std::string& name() const { return name_; }
};
class PropertyList {
    std::vector<Property> values_;

public:
    PropertyList() = default;
    PropertyList(std::initializer_list<Property> values) : values_(values) {}
    const Property& operator[](const std::string& name) const {
        for (const auto& value : values_)
            if (value.name() == name)
                return value;
        throw std::runtime_error("Missing argument");
    }
    size_t size() const { return values_.size(); }
};
class McpServer {
public:
    struct Tool {
        std::string description;
        PropertyList properties;
        std::function<ReturnValue(const PropertyList&)> callback;
    };
    std::map<std::string, Tool> tools;
    static McpServer& GetInstance() {
        static McpServer server;
        return server;
    }
    void AddTool(const std::string& name, const std::string& description,
                 const PropertyList& properties,
                 std::function<ReturnValue(const PropertyList&)> callback) {
        tools.insert_or_assign(name, Tool{description, properties, callback});
    }
};
#endif
