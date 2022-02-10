from time import sleep

from funcx import ContainerSpec, FuncXClient

fxc = FuncXClient(funcx_service_address="http://localhost:5000/v2")

container_uuid = fxc.build_container(
    ContainerSpec(
        name="MyContainer",
        # apt=[
        #     "dvipng",
        #     "ghostscript",
        #     "texlive-fonts-recommended",
        #     "texlive-generic-recommended",
        #     "cm-super",
        # ],
        pip=[
            # "cycler==0.10.0",
            # "kiwisolver==1.2.0",
            "matplotlib==6.2.1",
            "numpy==1.18.5",
        ],
    )
)

print(f"Building {container_uuid}")

while True:
    status = fxc.get_container_build_status(container_uuid)
    print(f"status is {status}")
    if status == 'ready':
        break
    sleep(5)

print(fxc.get_container(container_uuid, container_type="docker"))
