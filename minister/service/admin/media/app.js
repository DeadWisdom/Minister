Service = new Tea.Class({
    options: {
        name: 'Unnamed Service',
        
    }
})

Icon = Tea.Element.subclass({
    options: {
        cls: 'icon',
        type: '',
        status: 'active',
        colors: {
            "active":       "green",
            "struggling":   "green",
            "updating":     "gray",
            "deploying":    "gray",
            "redeploying":  "gray",
            "withdrawing":  "gray",
            "disabled":     "gray",
            "unknown":      "gray",
            "failed":       "red",
            "mia":          "red"
        }
    },
    preload : function(type)
    {
        if (Icon.preloaded[type])
            return;
        
        Icon.preloaded[type] = true;
        
        for(var status in this.colors)
        {
            var img = new Image();
            img.src = App.root + 'static/icons/' + type + '-' + this.colors[status] + '.png';
            console.log(img.src);
        }
    },
    setValue : function(status, type)
    {
        if (type)
            this.preload(type);
        
        this._img = App.root + 'static/icons/' + type + '-' + this.colors[status] + '.png';
        if (this.source)
            this.source.css('background-image', "url(" + this._img + ")");
    },
    onRender : function()
    {   
        if (this._img)
            this.source.css('background-image', this._img);
        else
            this.setValue(this.status, this.type);
    }
});
Icon.preloaded = {};

ServiceItem = Tea.Container.subclass({
    options: {
        cls: 'service item',
        value: null
    },
    __init__ : function(options)
    {
        this.__super__(options);
        
        this.value.bind('update', Tea.method(this.refresh, this));
        
        this.icon = new Icon();
        this.name = new Tea.Element({cls: 'name'});
        this.url =  new Tea.Element({cls: 'url'});
        this.info = new Tea.Element({cls: 'info'});
        
        this.append(this.icon);
        this.append(this.name);
        this.append(this.url);
        this.append(this.info);
    },
    onRender : function()
    {
        this.refresh();
    },
    refresh : function()
    {
        var v = this.value;
        
        this.source.attr('class', 'service item ' + v.status + ' ' + v.type);
        
        this.icon.setValue(v.status, v.type);
        this.name.setHTML(v.name);
        this.url.setHTML(v.url);
        if (v.statusText)
            this.info.setHTML(v.status + " &ndash; " + v.statusText);
        else
            this.info.setHTML(v.status);
    },
    setFail : function()
    {
        this.icon.setValue('unknown', this.value.type);
        this.source.attr('class', 'service item unknown');
        this.info.setHTML('unkown');
    }
});

LoadingElement = Tea.Element.subclass({
    options: {
        cls: 'loading item',
        value: null
    },
    onRender : function()
    {
        $('<div class="loading-icon icon"/>').appendTo(this.source);
        
        $('<div class="name">')
          .append("Loading")
          .appendTo(this.source);
    }
})

var App = new Tea.Application({
    stack: new Tea.StackContainer({ 
        skin: Tea.StackContainer.StretchySkin,
        column_width: 300
    }),
    
    ready : function()
    {
        this.stack.render().appendTo('#main');
        
        this.service_panel = new Tea.Panel({title: 'Services'});
        this.service_panel.append( this.loading = new LoadingElement() );
        this.stack.push( this.service_panel );
        
        this.services = new Tea.Resource({
            url: this.root + "services",
            key: 'path'
        });
        
        this.refresh = Tea.latent(1000, this._refresh, this);
        
        this.services.bind('update', Tea.method(this.update, this));
        this.services.bind('error', Tea.method(this.fail, this));
        this.services.query();
    },
    
    update : function(services)
    {
        this.service_panel.remove( this.loading );
        
        var list = this.services.popNew();
        for(var i = 0; i < list.length; i++)
        {
            var item = new ServiceItem({
                value: list[i]
            });
            this.service_panel.append(item);
        }
        
        this.refresh();
    },
    
    _refresh : function()
    {
        this.services.query();
    },
    
    fail : function()
    {
        jQuery.each(this.service_panel.items, function()
        {
            this.setFail();
        });
                
        this.refresh();
    },
    
    onLoad : function(services, status_code, request)
    {
        if (services == null)
        {
            this.timer = setTimeout(Tea.method(this.load, this), 3000);
            return this.onFail();
        }
        
        this.service_panel.remove( this.loading );
        
        var all = {};
        for(var i=0; i<services.length; i++)
        {
            this.setService(services[i]);
            all[services[i].path] = true;
        }
        
        for(var path in this.services)
        {
            if (!all[path])
            {
                this.services[path].remove();
                delete this.services[path];
            }
        }
        
        this.timer = setTimeout(Tea.method(this.load, this), 1000);
    },
    
    onFail : function()
    {
    },
    
    setService : function(value)
    {
        if (this.services[value.path])
        {
            this.services[value.path].setValue(value);
        }
        else
        {
            var d = this.services[value.path] = new ServiceItem({
                value: value
            });
            this.service_panel.append(d);
        }
    }
})