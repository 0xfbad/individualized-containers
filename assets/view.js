CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;
CTFd._internal.challenge.preRender = function () {};
CTFd._internal.challenge.render = null;
CTFd._internal.challenge.postRender = function () {};

CTFd._internal.challenge.submit = function (preview) {
    const challengeId = parseInt(CTFd.lib.$("#challenge-id").val());
    const submission = CTFd.lib.$("#challenge-input").val();
    const alert = resetAlert();

    const body = {
        challenge_id: challengeId,
        submission: submission,
    };

    const params = preview ? { preview: true } : {};

    return CTFd.api.post_challenge_attempt(params, body).then((response) => {
        if (response.status === 429 || response.status === 403) {
            return response;
        }
        return response;
    });
};

function mergeQueryParams(parameters, queryParameters) {
    if (parameters.$queryParameters) {
        Object.keys(parameters.$queryParameters).forEach((paramName) => {
            queryParameters[paramName] = parameters.$queryParameters[paramName];
        });
    }

    return queryParameters;
}

function resetAlert() {
    const alert = document.getElementById("deployment-info");
    alert.innerHTML = "";
    alert.classList.remove("alert-danger");

    return alert;
}

function toggleChallengeCreate() {
    const btn = document.getElementById("create-chal");
    btn.classList.toggle('d-none');
}

function toggleChallengeUpdate() {
    const btnExtend = document.getElementById("extend-chal");
    const btnTerminate = document.getElementById("terminate-chal");
    btnExtend.classList.toggle('d-none');
    btnTerminate.classList.toggle('d-none');
}

function calculateExpiry(expiresAtTimestamp) {
    const now = Date.now(); 
    const difference = Math.floor((expiresAtTimestamp * 1000 - now) / 1000);

    return difference > 0 ? difference : 0;
}

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const hoursStr = hours > 0 ? String(hours).padStart(2, '0') + ':' : '';
    const minutesStr = String(minutes).padStart(2, '0');
    const secondsStr = String(secs).padStart(2, '0');

    return hoursStr + `${minutesStr}:${secondsStr}`;
}

function createChallengeLinkElement(data, parent) {
    const expires = document.createElement('span');
    parent.append(expires, document.createElement('br'));

    const connectionDetails = document.createElement('div');
    parent.append(connectionDetails);

    function updateExpiry() {
        const secondsLeft = calculateExpiry(data.expires);

        expires.textContent = secondsLeft > 0 
            ? `Instance will expire in ${formatTime(secondsLeft)}` 
            : "Instance has expired";

        if (secondsLeft <= 0) {
            clearInterval(expiryInterval);

            toggleChallengeCreate();
            toggleChallengeUpdate();

            connectionDetails.innerHTML = '';
        }
    }

    updateExpiry();
    const expiryInterval = setInterval(updateExpiry, 1000);

    if (data.connect === "tcp") {
        const codeElement = document.createElement('code');
        codeElement.textContent = `nc ${data.hostname} ${data.port}`;
        connectionDetails.append(codeElement);
    } else if (data.connect === "ssh") {
        const codeElement = document.createElement('code');
        codeElement.textContent = data.ssh_password 
            ? `sshpass -p ${data.ssh_password} ssh -o StrictHostKeyChecking=no ${data.ssh_username}@${data.hostname} -p ${data.port}`
            : `ssh -o StrictHostKeyChecking=no ${data.ssh_username}@${data.hostname} -p ${data.port}`;
        connectionDetails.append(codeElement);
    } else {
        const link = document.createElement('a');
        link.href = `http://${data.hostname}:${data.port}`;
        link.textContent = link.href;
        link.target = '_blank';
        connectionDetails.append(link);
    }
}


function view_container_info(challengeId) {
    resetAlert();
    const alert = document.getElementById("deployment-info");

    fetch("/containers/api/view_info", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": init.csrfNonce,
        },
        body: JSON.stringify({ chal_id: challengeId }),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.status === "Instance not started") {
            alert.textContent = data.status;
            toggleChallengeCreate();
        } else if (data.status === "already_running") {
            createChallengeLinkElement(data, alert);
            toggleChallengeUpdate();
        } else {
            resetAlert();
            alert.textContent = data.message;
            alert.classList.add('alert-danger');
            toggleChallengeUpdate();
        }
    })
    .catch((error) => console.error("Fetch error:", error));
}

function container_request(challengeId) {
    const alert = resetAlert();

    fetch("/containers/api/request", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": init.csrfNonce,
        },
        body: JSON.stringify({ chal_id: challengeId }),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.error || data.message) {
            alert.textContent = data.error || data.message;
            alert.classList.add('alert-danger');
            toggleChallengeCreate();
        } else {
            createChallengeLinkElement(data, alert);
            toggleChallengeCreate();
            toggleChallengeUpdate();
        }
    })
    .catch((error) => console.error("Fetch error:", error));
}

function container_renew(challengeId) {
    const alert = resetAlert();

    fetch("/containers/api/renew", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": init.csrfNonce,
        },
        body: JSON.stringify({ chal_id: challengeId }),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.error || data.message) {
            alert.textContent = data.error || data.message;
            alert.classList.add('alert-danger');
            toggleChallengeCreate();
        } else {
            createChallengeLinkElement(data, alert);
        }
    })
    .catch((error) => console.error("Fetch error:", error));
}

function container_stop(challengeId) {
    const alert = resetAlert();

    fetch("/containers/api/stop", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": init.csrfNonce,
        },
        body: JSON.stringify({ chal_id: challengeId }),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.error || data.message) {
            alert.textContent = data.error || data.message;
            alert.classList.add('alert-danger');
            toggleChallengeCreate();
        } else {
            alert.textContent = "Instance terminated";
            toggleChallengeCreate();
            toggleChallengeUpdate();
        }
    })
    .catch((error) => console.error("Fetch error:", error));
}
