async function fetchData(url, method = "GET", headers = {}, body = null) {
    try {
        const options = {
            method,
            headers: {
                "Accept": "application/json",
                "CSRF-Token": init.csrfNonce,
                ...headers
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        const data = await response.json();

        if (data.error) {
            console.error("Error:", data.error);
            return null;
        }

        return data;
    } catch (error) {
        console.error("Fetch error:", error);
        return null;
    }
}

async function loadContainerImages() {
    const containerImage = document.getElementById("container-image");
    const containerImageDefault = document.getElementById("container-image-default");

    const data = await fetchData("/containers/api/images");

    if (!data) {
        containerImageDefault.innerHTML = "Failed to load images.";
        return;
    }

    data.images.forEach(image => {
        const opt = document.createElement("option");
        opt.value = image;
        opt.innerHTML = image;
        containerImage.appendChild(opt);
    });

    containerImageDefault.innerHTML = "Choose an image...";
    containerImage.removeAttribute("disabled");
    containerImage.value = container_image_selected;
}

async function loadConnectType(challengeId) {
    const connectType = document.getElementById("connect-type");
    const connectTypeDefault = document.getElementById("connect-type-default");

    const data = await fetchData(`/containers/api/get_connect_type/${challengeId}`);

    if (!data) {
        connectTypeDefault.innerHTML = "Failed to load connect type.";
        return;
    }

    connectTypeDefault.innerHTML = "Choose...";
    connectType.removeAttribute("disabled");
    connectType.value = data.connect;
}

function getChallengeIdFromURL() {
    const currentURL = window.location.href;
    const match = currentURL.match(/\/challenges\/(\d+)/);

    return match && match[1] ? parseInt(match[1]) : null;
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadContainerImages();

    const challengeId = getChallengeIdFromURL();

    if (challengeId) {
        await loadConnectType(challengeId);
    } else {
        console.error("Challenge ID not found in the URL.");
    }
});

