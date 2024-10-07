CTFd.plugin.run(async (_CTFd) => {
    const $ = _CTFd.lib.$;
    const md = _CTFd.lib.markdown();

    const containerImage = document.getElementById("container-image");
    const containerImageDefault = document.getElementById("container-image-default");

    try {
        const response = await fetch("/containers/api/images", {
            method: "GET",
            headers: {
                "Accept": "application/json",
                "CSRF-Token": init.csrfNonce
            }
        });

        if (!response.ok) throw new Error("Error fetching data");

        const data = await response.json();

        if (data.error) {
            containerImageDefault.textContent = data.error;
        } else {
            data.images.forEach(image => {
                const option = document.createElement("option");
                option.value = image;
                option.textContent = image;
                containerImage.appendChild(option);
            });

            containerImageDefault.textContent = "Choose an image...";
            containerImage.removeAttribute("disabled");
        }
    } catch (error) {
        console.error("Fetch error:", error);
        containerImageDefault.textContent = "Failed to load images.";
    }
});
