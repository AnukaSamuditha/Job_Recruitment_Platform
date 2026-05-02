CONTRACTS_ROOT ?= ../../contracts
PROTO_PATH = $(CONTRACTS_ROOT)/proto
OUT_DIR = app/gen

.PHONY: gen-grpc clean-gen

gen-grpc:
	python -m grpc_tools.protoc \
		-I "$(PROTO_PATH)" \
		--python_out=$(OUT_DIR) \
		--grpc_python_out=$(OUT_DIR) \
		--pyi_out=$(OUT_DIR) \
		"$(PROTO_PATH)/recruitment/v1/recruitment.proto"
	@python -c "import pathlib; p=pathlib.Path('$(OUT_DIR)/recruitment/v1'); p.mkdir(parents=True, exist_ok=True); open(p/'__init__.py','a').close(); pathlib.Path('$(OUT_DIR)/recruitment/__init__.py').touch()"

clean-gen:
	rm -rf app/gen/recruitment
