from funcx import FuncXClient, ContainerSpec

fxc = FuncXClient(funcx_service_address="http://localhost:5000/v2")
container_uuid = fxc.build_container(ContainerSpec(
    name="MyContainer",
    apt=["dvipng",
         "ghostscript",
         "texlive-fonts-recommended",
         "texlive-generic-recommended",
         "cm-super"],
    pip=[
        "cycler==0.10.0",
        "kiwisolver==1.2.0",
        "matplotlib==3.2.1",
        "numpy==1.18.5"
    ]
))

print(f"Building {container_uuid}")

print(f"status is {fxc.get_container_build_status(container_uuid)}")

