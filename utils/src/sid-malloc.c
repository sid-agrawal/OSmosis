/* titel: malloc()/free()-Paar nach K&R 2, p.185ff */

#include <stdlib.h>
#include <utils/sid-malloc.h>
#include <utils/sid-malloc.h>
#include <sel4utils/util.h>
typedef long Align;

 /* Statically allocated morecore area.
 *
 * This is rather terrible, but is the simplest option without a
 * huge amount of infrastructure.
 */

#define CONFIG_LIB_SEL4_MUSLC_SYS_MORECORE_BYTES (1024*64)
char __attribute__((aligned(PAGE_SIZE_4K))) morecore_area[CONFIG_LIB_SEL4_MUSLC_SYS_MORECORE_BYTES];

size_t morecore_size = CONFIG_LIB_SEL4_MUSLC_SYS_MORECORE_BYTES;
/* Pointer to free space in the morecore area. */
static uintptr_t morecore_base = (uintptr_t) &morecore_area;
uintptr_t morecore_top = (uintptr_t) &morecore_area[CONFIG_LIB_SEL4_MUSLC_SYS_MORECORE_BYTES];

/* Actual morecore implementation
   returns 0 if failure, returns newbrk if success.
*/

void * sbrk(size_t bytes)
{

    uintptr_t ret;
    static uintptr_t newbrk = (uintptr_t )NULL;

    printf("calling sbkr with a request of %ld\n", bytes);
    /*if the newbrk is 0, return the bottom of the heap*/
    if (!newbrk) {
        ZF_LOGE("sbrk for the first time, returning bottom of heap\n");
        ret = morecore_base;
        newbrk = morecore_base + bytes;
    } else if (newbrk + bytes < morecore_top) {
        ZF_LOGE("sbrk called with %p, returning %p\n", (void *) newbrk, (void *) newbrk + bytes);
        ret = newbrk;
        newbrk += bytes;
    } else {
        ZF_LOGF("sbrk called with %p, returning 0\n", (void *) newbrk);
        ret = 0;
    }
    printf("returning 0x%p from sbkr\n", (void *) ret);
    return (void *) ret;
}

union header {			/* Kopf eines Allokationsblocks */
    struct {
	union header	*ptr;  	/* Zeiger auf zirkulaeren Nachfolger */
	size_t 	size;	/* Groesse des Blocks	*/
    } s;
    Align x;			/* Erzwingt Block-Alignierung	*/
};

typedef union header Header;

static Header base;		/* Anfangs-Header	*/
static Header *freep = NULL;	/* Aktueller Einstiegspunkt in Free-Liste */

static Header *morecore(size_t nu);

void* malloc(size_t nbytes) {
    Header *p, *prevp;
    size_t nunits;

     /* Kleinstes Vielfaches von sizeof(Header), das die
	geforderte Byte-Zahl enthalten kann, plus 1 fuer den Header selbst: */

    nunits = (nbytes+sizeof(Header)-1)/sizeof(Header) + 1;

    if ((prevp = freep) == NULL) {	/* Erster Aufruf, Initialisierung */
	base.s.ptr = freep = prevp = &base;
	base.s.size = 0;		/* base wird Block der Laenge 0 */
    }
    for (p = prevp->s.ptr; ; prevp = p, p = p->s.ptr) {

	/* p durchlaeuft die Free-Liste, gefolgt von prevp, keine
		Abbruchbedingung!!	*/

	if (p->s.size >= nunits) {	/* Ist p gross genug? 		*/
	    if (p->s.size == nunits) 	/* Falls exakt, wird er... 	*/
		prevp->s.ptr = p->s.ptr;/* ... der Liste entnommen 	*/
	    else {			/* andernfalls...	   	*/
		p->s.size -= nunits;	/* wird p verkleinert		*/
		p += p->s.size;		/* und der letzte Teil ... 	*/
		p->s.size = nunits;	/* ... des Blocks...		*/
	    }
	    freep = prevp;
	    return (void*) (p+1);	/* ... zurueckgegeben, allerdings
					   unter der Adresse von p+1,
					   da p auf den Header zeigt.  	*/
	}
	if ( p == freep)		/* Falls die Liste keinen Block
				           ausreichender Groesse enthaelt,
					   wird morecore() aufgrufen	*/
	    if ((p = morecore(nunits)) == NULL)
		return NULL;
    }
}

#define NALLOC 	1024	/* Mindestgroesse fuer morecore()-Aufruf	*/

/* Eine static-Funktion ist ausserhalb ihres Files nicht sichtbar	*/

static Header *morecore(size_t nu)
{
    printf("calling morecore with a request for %ld bytes\n", nu);
    char *cp;
    void free(void *);
    Header *up;
    if (nu < NALLOC)
        nu = NALLOC;
    cp = sbrk(nu * sizeof(Header));
    if (cp == (char *)-1) /* sbrk liefert -1 im Fehlerfall */
        return NULL;
    up = (Header *)cp;
    up->s.size = nu;        /* Groesse wird eingetragen	*/
    free((void *)(up + 1)); /* Einbau in Free-Liste		*/
    return freep;
}

void free(void *ap) {			/* Rueckgabe an Free-Liste	*/
    Header *bp, *p;

    bp = (Header*) ap - 1;		/* Hier ist der Header des Blocks */

	/* Die Liste wird durchmustert, der Block soll der
	   Adressgroesse nach richtig eingefuegt werden,
	   um Defragmentierung zu ermoeglichen.				*/

    for (p = freep; !(bp > p && bp < p->s.ptr); p = p->s.ptr)
	if (p >= p->s.ptr && (bp > p || bp < p->s.ptr))
	    break;	/* bp liegt vor Block mit kleinster oder hinter
			   Block mit groesster Adresse */

    if (bp + bp->s.size == p->s.ptr) {
				/* Vereinigung mit oberem Nachbarn 	*/
	bp->s.size += p->s.ptr->s.size;
	bp->s.ptr = p->s.ptr->s.ptr;
    }
    else
	bp->s.ptr = p->s.ptr;
    if ( p + p->s.size == bp ) {
				/* Vereinigung mit unterem Nachbarn 	*/
	p->s.size += bp->s.size;
	p->s.ptr = bp->s.ptr;
    } else
	p->s.ptr = bp;
    freep = p;
}

void *calloc(size_t n, size_t size) {
    void *p;
    size_t nbytes = n * size;
    p = malloc(nbytes);
    if (p != NULL)
    memset(p, 0, nbytes);
    return p;
}
