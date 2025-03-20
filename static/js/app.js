function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

document.addEventListener("alpine:init", () => {
    Alpine.data("app", () => ({
        query: '',
        selected_collection: '',
        collections: [],
        results: [],
        answer: {
            show: false,
            tokens: [],
            output_index: 0,
            id: '',
            html: '',
            complete: false
        },
        thinking: true,
        splash: true,
        modal: {
            show: false,
            item: '',
            type: '',
            text: '',
        },
        toast: {
            show: false,
            title: 'Toast Title',
            msg: 'Toast Message',
        },
        privacyNotice: {
            show: true,
        },
        async search() {
            this.splash = false;
            this.thinking = true;
            this.ragSearch(this);
            try {
                const response = await fetch(`/query/semantic?q=${this.query}&collection=${this.selected_collection}`);
                this.results = await response.json();
            } catch (e) {
                console.error(e);
            } finally {
                this.thinking = false;
            }
        },
        async pollRag() {
            while (!this.answer.complete) {
                await sleep(500); //Poll server every 500ms
                const response = await fetch(`/query/rag?id=${this.answer.id}`);
                const rag_response = await response.json();
                this.answer.id = rag_response.id;
                this.answer.tokens = rag_response.tokens;
                this.answer.complete = rag_response.complete;
                this.answer.show = this.answer.tokens.length > 0;
            }
        },
        async updateRagOutput() {
            while (!this.answer.complete) {
                console.log("output_index=" + this.answer.output_index + " tokens.length=" + this.answer.tokens.length);
                if (this.answer.output_index < this.answer.tokens.length) {
                    while (this.answer.output_index < this.answer.tokens.length) {
                        tokens_to_show = this.answer.tokens.slice(0, this.answer.output_index).join("");
                        this.answer.content = marked.parse(tokens_to_show);
                        this.answer.output_index++;
                        await sleep(30);
                    }
                }
                await sleep(300); //RAG output exausted, sleep for a bit before polling again
            }
        },
        async ragSearch() {
            try {
                this.answer = { id: '', content: '', complete: false, show: false, output_index: 0, tokens: [] };
                const response = await fetch(`/query/rag?q=${this.query}&collection=${this.selected_collection}`, { method: 'POST' });
                const rag_response = await response.json();
                this.answer.id = rag_response.id;
                this.answer.content = rag_response.content;
                this.answer.complete = rag_response.complete;
                this.answer.tokens = rag_response.tokens;
                Promise.all([this.pollRag(), this.updateRagOutput()]);
            } catch (e) {
                console.error(e);
            }
        },
        async get_collections() {
            try {
                const response = await fetch(`/collections/list`);
                const result = await response.json();
                this.collections = result;
                if (this.collections.length > 0)
                    this.selected_collection = this.collections[0];
                this.thinking = false;
            } catch (e) {
                console.error(e);
            }
        },
        async feedback(event) {
            console.log('Giving feedback...');
            console.log(event.target);
        },
        async submit_feedback_modal(item, itemType, query, feedback, type) {
            if (feedback.length < 10) {
                this.showToast('Feedback Error', 'Feedback must be at least 10 characters long');
                return;
            }
            this.give_feedback(item, itemType, query, feedback, type);
            this.modal.text = '';
            this.closeModal();
        },
        async give_feedback(item, itemType, query, feedback, feedbackType) {
            const feedback_obj = { "query": query, "item": item, "itemType": itemType, "feedback": feedback, "type": feedbackType };
            console.log(feedback_obj);
            const response = await fetch(`/feedback/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(feedback_obj),
            });
            const result = await response.json();
            this.showToast('Feedback Submitted', feedbackType + ':"' + feedback + '" for: ' + JSON.stringify(item));
        },
        showToast(title, msg) {
            this.toast.show = true;
            this.toast.title = title;
            this.toast.msg = msg;
            setTimeout(() => {
                this.toast.show = false;
            }, 4000);
        },
        openModal(item, type) {
            this.modal.item = item;
            this.modal.type = type;
            this.modal.show = true;
        },
        closeModal() {
            this.modal.show = false;
        },
        openPrivacyNotice() {
            this.privacyNotice.show = true;
        }
        ,
        closePrivacyNotice() {
            this.privacyNotice.show = false;
        }
    }))
})
