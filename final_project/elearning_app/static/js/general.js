function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function logoutUser() {
    try {
        const response = await fetch("/api/logout/", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
            refresh: localStorage.getItem("refresh")
            }),
        });

        // Regardless of success, clear tokens and redirect to home
        localStorage.removeItem("access");
        localStorage.removeItem("refresh");

        window.location.href = "/";
    } catch (error) {
        console.error("Logout failed", error);
        window.location.href = "/"; // fallback
    }
}

async function startChat(user_ids) {
    try {
        const response = await fetch("/api/chats/", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                user_ids: user_ids
            }),
        });

        if (response.ok) {
            const chatData = await response.json();
            console.log(chatData);
            window.location.href = `/chats/${chatData.pk}`;
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not start chat. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to start chat");
    }
}

async function enroll(user_id, course_id) {
    try {
        console.log(user_id, course_id)
        if (!user_id) {
            window.location.href = '/login';
        }

        const response = await fetch(`/api/courses/${course_id}/enrollments/`, {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                user_id: user_id,
            }),
        });

        if (response.ok) {
            const enrollmentData = await response.json();
            console.log(enrollmentData);
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not enroll user in course. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to enroll user in course");
    }
}

async function dismissNotification(notificationId) {
    try {
        const response = await fetch(`/api/notifications/${notificationId}/dismiss/`, {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not dismiss notification. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to dismiss notification");
    }
}

async function updateLessonCompletion(lessonId, completed) {
    try {
        const response = await fetch(`/api/lessons/${lessonId}/progress/`, {
            method: "PUT",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                "completed": completed
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not update lesson completion. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to update lesson completion");
    }
}

async function updateEnrollmentStatus(enrollmentId, status) {
    try {
        const response = await fetch(`/api/courses/enrollments/${enrollmentId}/`, {
            method: "PATCH",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                status: status
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not remove student's enrollment. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to remove student's enrollment");
    }
}

async function blockUser(blockedById, blockedUserId) {
    try {
        const response = await fetch(`/api/users/block/`, {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                blocked_by: blockedById,
                blocked_user: blockedUserId
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not block user. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to block user");
    }
}


async function unblockUser(blockedById, blockedUserId) {
    try {
        const response = await fetch(`/api/users/block/`, {
            method: "DELETE",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                blocked_by: blockedById,
                blocked_user: blockedUserId
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not unblock user. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to unblock user");
    }
}

async function publishCourse(courseId) {
    try {
        const response = await fetch(`/api/courses/${courseId}/`, {
            method: "PATCH",
            headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken'),
            },
            body: JSON.stringify({
                is_published: true
            })
        });

        if (response.ok) {
            window.location.reload();
        } else {
            const errorData = await response.json();
            console.error('Error: ', errorData.error);
            alert("Could not publish course. Please try again");
        }

    } catch (error) {
        console.error("Error: ", error);
        alert("Failed to publish course");
    }
}